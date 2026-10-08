# -*- coding: utf-8 -*-
"""
Leitura da Ficha Disciplinar do SIAPEN (AGEPEN/MS) e confronto com o RSPE.

Extrai: identificação, conduta, períodos de trabalho (setor/empresa), atestados de trabalho
(dias trabalhados e remidos), faltas disciplinares (registro, PADIC, resultado), regressão/
restabelecimento e recusa de trabalho. Compara os dias remidos atestados com o saldo do RSPE
(LEP, arts. 126 a 128) e a existência de falta grave (LEP, art. 50; CP, art. 83, III, b).
"""
import math
import re
from datetime import date, timedelta

import pdfplumber

import rspe_scraper as rs

RE_LINHA = re.compile(r"(?m)^(\d{2}\.\d{2}\.\d{4}) - ")
RE_D = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")


def _d(txt):
    m = RE_D.search(txt or "")
    if not m:
        return None
    dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yy < 100:
        yy += 2000 if yy < 70 else 1900
    try:
        return date(yy, mm, dd)
    except ValueError:
        return None


def _dp(txt):
    try:
        d = date(int(txt[6:10]), int(txt[3:5]), int(txt[0:2]))
        return d if 1900 <= d.year <= 2100 else None
    except Exception:
        return None


def _num(txt):
    """Número da ficha ('4,33', '4.33...', '12'): só a parte numérica; 0 se não houver."""
    m = re.search(r"\d+(?:[.,]\d+)?", str(txt or ""))
    return float(m.group(0).replace(",", ".")) if m else 0.0


def texto_pdf(caminho):
    with pdfplumber.open(caminho) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def texto_pagina1(caminho):
    with pdfplumber.open(caminho) as pdf:
        return (pdf.pages[0].extract_text() or "") if pdf.pages else ""


def e_ficha(texto):
    # tolerante a espaços e quebras de linha no título e ao cabeçalho do sistema (SIAPEN ou AGEPEN)
    t = re.sub(r"\s+", " ", (texto or "").upper())
    return bool(re.search(r"FICHA ?DISCIPLINAR", t)) and ("SIAPEN" in t or "AGEPEN" in t or "PENITENCI" in t)


def _limpar(t):
    # remove cabeçalhos/rodapés repetidos do SIAPEN
    out = []
    for l in t.splitlines():
        u = l.strip()
        if not u:
            continue
        if re.search(r"Confidencial ::|Responsável:|Projeto SIAPEN|^RUA:|^CEP:|^FONE:|^\d{2}:\d{2}:\d{2}$|^RRMB|^\d{2}:\d{2}: ", u):
            continue
        # login de quem imprimiu, no topo de cada página ("RSS (8002969) em: 02/10/2026"): sozinho ou colado no fim da linha
        u = re.sub(r"\s*\b[A-Z0-9]{2,12}\s*\(\d{5,}\)\s*em:\s*\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s*$", "", u)
        if not u:
            continue
        out.append(u)
    return "\n".join(out)


MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "MARCO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8,
         "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}


def _estudos(eventos):
    """Períodos de estudo da ficha (LEP, art. 126, § 1º, I): matrícula -> cancelamento/encerramento, por série/curso.
    Cursos em texto livre (ex.: "CURSO DE BARBEIRO/SENAC 40H ... 09 DE AGOSTO 2021 A 20 DE AGOSTO 2021") viram um período
    com a carga horária declarada."""
    import rspe_remicao as rrm
    out, abertos = [], []

    def fechar(p, data, motivo):
        p["fim"], p["motivo_fim"] = data, motivo
        abertos.remove(p)

    def abrir(nome, data, turno=""):
        for p in [p for p in abertos if not p.get("livre")]:
            fechar(p, data, "nova matrícula" if p["curso"] == nome else "nova matrícula em outra série")
        p = {"curso": nome, "turma": "", "turno": turno, "inicio": data, "fim": "", "motivo_fim": "", "horas": None}
        abertos.append(p); out.append(p)

    for e in eventos:
        u = e["texto"].upper()
        us = rs._sem_acento(u)
        if not re.search(r"EDUCA|\bCURSO\b|ESCOLA|ESTUD|ALUNOS", us):
            continue
        ua = re.sub(r"\s+", " ", us)
        if re.search(r"ATESTADO|\bATP\b", ua) and (rrm.RE_AT_ESTUDO.search(rrm._norm_at(ua)) or re.search(r"FREQUENCIA ESCOLAR", ua)) \
                and not re.search(rrm.NDIAS + r"\s*DIAS\s*TRABALHAD", ua):
            # atestado de estudo ("Tipo: Estudante; Data Inicial: d; Data Final: d; Tempo de Estudo: 329 h/a", "tempo de estudo 400h",
            # "frequência escolar ... 400 h/a"): período com as horas atestadas; o mesmo atestado lançado de novo conta uma vez
            ua = rrm._norm_at(ua)
            mp = re.search(r"DATA INICIAL\W*(\d{2}[./]\d{2}[./]\d{4})\W*(?:DATA FINAL|ATE)\W*(\d{2}[./]\d{2}[./]\d{4})", ua) or \
                re.search(r"(\d{2}[./]\d{2}[./]\d{4})\s*(?:A|ATE|-)\s*(\d{2}[./]\d{2}[./]\d{4})", ua)
            mh = re.search(r"(?:ESTUDO|CARGA HORARIA|TOTALIZANDO|HORAS)\D{0,25}?(\d+)\s*/?\s*(?:H/A|H\b|HORAS)|(\d+)\s*/?\s*H/A", ua)
            if mh:
                ini = rrm._dt(mp.group(1)).strftime("%d.%m.%Y") if mp and rrm._dt(mp.group(1)) else e["data"]
                fim = rrm._dt(mp.group(2)).strftime("%d.%m.%Y") if mp and rrm._dt(mp.group(2)) else ""
                nat = re.search(r"\bATP\s*(?:N\S*\s*)?(\d+/\d+)|ATESTADO\D{0,30}?N?\W{0,3}(\d+/\d+)", ua)
                num = (nat.group(1) or nat.group(2)) if nat else ""
                p = {"curso": "Atestado de estudo" + (" nº " + num if num else ""), "turma": "", "turno": "", "inicio": ini, "fim": fim or ini,
                     "motivo_fim": "atestado de estudo" if fim else "carga horária declarada", "horas": int(mh.group(1) or mh.group(2)), "livre": True}
                if not any(x.get("livre") and ((num and x["curso"] == p["curso"]) or (x["inicio"], x["fim"], x["horas"]) == (p["inicio"], p["fim"], p["horas"])) for x in out):
                    out.append(p)
            continue
        if re.search(r"PETICIONAD|PROTOCOLAD|ENTREGUE|PARECER|ATESTADO DE PERMANENCIA|CERTIFICADO|CERTIDAO", us):
            continue  # documento (certidão, certificado, curso peticionado): não abre nem fecha período
        # setor de trabalho "Escola" (estudo lançado como trabalho)
        mt_ = re.search(r"TRABALHO: (INICIOU ATIVIDADE LABORAL|DEIXA DE TRABALHAR), NO SETOR DE TRABALHO (ESCOLA[^,]*?)\s*,", us)
        if mt_:
            if mt_.group(1).startswith("INICIOU"):
                abrir(mt_.group(2).strip().title(), e["data"])
            else:
                for p in [p for p in abertos if p["curso"].upper() == mt_.group(2).strip()]:
                    fechar(p, e["data"], "deixou a escola")
            continue
        if "TRABALHO" in u and not re.search(r"\bCURSO\b|MATRICUL", us):
            continue
        if re.search(r"TERMO DE AFASTAMENTO DOS ESTUDOS|MATRICULA ESCOLAR ENCERRADA", us):
            for p in list(abertos):
                fechar(p, e["data"], "afastamento dos estudos" if "AFASTAMENTO" in us else "matrícula encerrada")
            continue
        # matrícula em texto livre: "Matriculou-se: MODULO – EJA ...", "Foi matriculado na escola ... para estudar o módulo X"
        mm_ = re.search(r"MATRICULOU-SE:\s*([^,.]+)|FOI MATRICULADO NA ESCOLA\b(?:.*?(?:ESTUDAR O|NO)\s+(MODULO[^,.]*))?", us)
        if mm_:
            if any(x is not e and x["data"] == e["data"] and re.search(r"MATRICULOU-SE NA SERIE", rs._sem_acento(x["texto"]).upper()) for x in eventos):
                continue  # a matrícula do dia já está lançada no formato do SIAPEN
            abrir(re.sub(r"\s+(?:NO )?PERIODO.*$", "", (mm_.group(1) or mm_.group(2) or "ESCOLA")).strip(" .-–"), e["data"])
            continue
        # início em texto livre: setor escolar / setor educacional / rol de alunos / atividades escolares
        mi = re.search(r"INICIOU NO SETOR ESCOLAR|PASSA A FREQUENTAR O SETOR EDUCACIONAL(?: NO| NA)?\s*([^,.]*)|INCLUIDO NO ROL DE ALUNOS[^,;]*?(?:MATRICULADO NA|[,;]\s*NA)\s+([^,.]+)|"
                       r"COMECOU SUAS ATIVIDADES ESCOLARES|INICIA ATIVIDADES (?:ESCOLARES|PEDAGOGICAS)", us)
        if mi:
            nome = next((g for g in mi.groups() if g and g.strip()), "") or "Setor escolar"
            abrir(nome.strip(" .-").upper(), e["data"])
            continue
        if re.search(r"DEIXA DE (?:ESTUDAR|FREQUENTAR O SETOR DE EDUCA)", us):
            for p in list(abertos):
                fechar(p, e["data"], "deixou de estudar")
            continue
        m = re.search(r"MATR[ÍI]CULOU-SE NA S[ÉE]RIE:\s*(.+?)\s+TURMA:\s*(.*?)\s*PER[ÍI]ODO:\s*(.*)$", u)
        if m and re.search(r"DESISTEN|AFASTADO|TRANSFERID|EVADID|AGUARDANDO|TRIAGEM|ESPERA|CLASSIFICACAO", rs._sem_acento(m.group(1))):
            # o SIAPEN registra a desistência e a espera por vaga ("AGUARDANDO CURSO", "TRIAGEM/CLASSIFICAÇÃO") como "série": não há estudo
            for p in list(abertos):
                fechar(p, e["data"], m.group(1).strip(" .-").lower())
            continue
        if m:
            serie = m.group(1).strip(" .-")
            for p in [p for p in abertos if p["curso"] == serie]:
                fechar(p, e["data"], "nova matrícula na mesma série")
            for p in [p for p in abertos if not p.get("livre")]:
                fechar(p, e["data"], "nova matrícula em outra série")  # o aluno cursa uma série por vez
            p = {"curso": serie, "turma": m.group(2).strip(" .") , "turno": m.group(3).strip(" ."), "inicio": e["data"], "fim": "", "motivo_fim": "", "horas": None}
            abertos.append(p); out.append(p)
            continue
        m = re.search(r"MATRICULA CANCELADA\W*(?:SERIE:\s*(.+?)(?:\s+PERIODO|\s*-|$))?", us)
        if m:
            serie = (m.group(1) or "").strip(" .-")
            alvo = [p for p in abertos if p["curso"] == serie] or abertos[-1:]
            for p in alvo:
                fechar(p, e["data"], "matrícula cancelada")
            continue
        if re.search(r"CANCELAMENTO DE MATR[ÍI]CULA|CONCLU[ÍI]U|CONCLUS[ÃA]O DO CURSO", u):
            for p in list(abertos):
                fechar(p, e["data"], "concluído" if "CONCLU" in u else "matrícula cancelada" + (" (saída da unidade)" if "SA" in u and "PRES" in u else ""))
            continue
        if re.search(r"\bCURSO\b", us) or re.match(r"EDUCACAO:.*\d{2}/\d{2}/\d{4}\s*(?:A|ATE)\s*\d{2}/\d{2}/\d{4}.*\d+\s*(?:H\b|HS\b|HORAS)", us):
            h = re.search(r"(?<![:\d])(\d+)\s*(?:H\b|HS\b|HORAS)", u)
            per = re.search(r"(\d{1,2})\s+DE\s+([A-ZÇ]+)\s+(?:DE\s+)?(\d{4})\s+(?:A|À|ATÉ)\s+(\d{1,2})\s+DE\s+([A-ZÇ]+)\s+(?:DE\s+)?(\d{4})", u)
            ini, fim = e["data"], ""
            pn = re.search(r"(\d{2}/\d{2}/\d{4})\s*(?:A|À|ATÉ)\s*(\d{2}/\d{2}/\d{4})", u)  # "no período de 29/07/2024 a 01/08/2024"
            mi_ = re.search(r"IN[IÍ]CIO\W*(\d{1,2})\s+DE\s+([A-ZÇ]+)\s+(?:DE\s+)?(\d{4})", u)  # "Início 10 de março de 2020"
            if pn and _d(pn.group(1)) and _d(pn.group(2)):
                ini, fim = _d(pn.group(1)).strftime("%d.%m.%Y"), _d(pn.group(2)).strftime("%d.%m.%Y")
            elif mi_ and mi_.group(2) in MESES and _dp("%02d.%02d.%s" % (int(mi_.group(1)), MESES[mi_.group(2)], mi_.group(3))):
                ini = "%02d.%02d.%s" % (int(mi_.group(1)), MESES[mi_.group(2)], mi_.group(3))
            if per and per.group(2) in MESES and per.group(5) in MESES:
                ini2 = "%02d.%02d.%s" % (int(per.group(1)), MESES[per.group(2)], per.group(3))
                fim2 = "%02d.%02d.%s" % (int(per.group(4)), MESES[per.group(5)], per.group(6))
                if _dp(ini2) and _dp(fim2):  # data impossível (ex.: 31 de junho): fica a data do registro
                    ini, fim = ini2, fim2
            nome = (re.search(r"CURSO (?:DE )?([A-ZÇÃÕÁÉÍÓÚ/ ]+?)(?:\s+\d|,|\.|$)", u) or
                    re.search(r"^EDUCA[ÇC][ÃA]O:\s*([A-ZÇÃÕÁÉÍÓÚ/ ]+?)(?:\s+REALIZADO|\s+NO PER|,|\.|$)", u) or [None, "curso"])[1].strip()
            chave = re.sub(r"\W", "", nome)[:5]
            # o mesmo curso citado de novo (ex.: início remarcado) substitui o registro anterior; curso sem nome não se confunde com outro
            ant = [p for p in out if p.get("livre") and re.sub(r"\W", "", p["curso"])[:5] == chave and nome != "curso"]
            for p in ant:
                out.remove(p)
                if p in abertos:
                    abertos.remove(p)
            if not fim and not h:
                continue  # curso citado sem período nem carga horária: não há o que contar (evita período aberto até hoje)
            if any(p.get("livre") and (p["curso"], p["inicio"], p["fim"], p["horas"]) == (nome, ini, fim or ini, int(h.group(1)) if h else None) for p in out):
                continue  # o mesmo curso lançado de novo
            out.append({"curso": nome, "turma": "", "turno": "", "inicio": ini, "fim": fim or ini, "motivo_fim": "período do curso" if fim else "carga horária declarada",
                        "horas": int(h.group(1)) if h else None, "livre": True})
    ult = max((_dp(e["data"]) for e in eventos if re.search(r"EDUCA|ESCOLA|ESTUD|FREQUENCIA|MATRICUL", rs._sem_acento(e["texto"].upper())) and _dp(e["data"])), default=None)
    for p in abertos:
        p["ult_registro_edu"] = ult.strftime("%d.%m.%Y") if ult else ""
    return out


def _arts_lep(u):
    """Artigos da LEP citados no lançamento ("... ART 79 ... DO RIBUP E ARTIGOS 39, INCISOS I E VI E 50, INCISO VI E VII, DA LEP"):
    os números arábicos entre o último "ART" e cada menção à LEP (os incisos vêm em romanos). O art. 50 (e o 52) é falta grave,
    ainda que o primeiro artigo citado seja do regimento (RIBUP)."""
    out = set()
    for m in re.finditer(r"\b(?:DA|DO|NA)\s+(?:LEP\b|LEI\s*(?:N\W{0,3}\s*)?7\.?210|LEI DE EXECU)", u):
        antes = u[max(0, m.start() - 160):m.start()]
        k = antes.rfind("ART")
        if k >= 0:
            out |= set(re.findall(r"\b(\d{1,3})\b", re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}|\d+\.\d{3}", " ", antes[k:])))
    return out


def _artigo_falta(u):
    """Rótulo do artigo da falta: o da LEP citado ("art. 50, VI e VII, da LEP"; o 50/52 primeiro), senão o primeiro artigo, com a
    lei certa ("art. 79 do RIBUP"). O art. 60 da LEP (fundamento do registro) não é o da falta."""
    u = rs._sem_acento(u).upper()
    k = u.find("INFRING")
    t = u[k:] if k >= 0 else u

    def incisos(n):
        mi = re.search(r"\b%s\b\s*[,º°]?\s*,?\s*(?:(?:INCISOS?|INC\.?)\s*)?([IVXL]+\b(?:\s*(?:,|\bE\b)\s*[IVXL]+\b)*)" % n, t)
        if not mi:
            return ""
        xs = re.findall(r"[IVXL]+", mi.group(1))
        return ", " + (", ".join(xs[:-1]) + " e " + xs[-1] if len(xs) > 1 else xs[0])
    lep = _arts_lep(t) - {"60"}
    m0 = re.search(r"INFRING\w*\s*(?:EM TESE)?\s*:?\s*O?\s*ART(?:IGO)?\.?\s*(5[02])\b", t)  # "infringido o art. 50, ... c/c art. 39 da Lei 7.210"
    lep = sorted(lep | ({m0.group(1)} if m0 else set()), key=int)
    lep = [n for n in lep if n in ("50", "52")] or lep
    if lep:
        return "art%s. %s, da LEP" % ("s" if len(lep) > 1 else "", " e ".join("%s%s" % (n, incisos(n)) for n in lep)) if any(incisos(n) for n in lep) \
            else "art%s. %s da LEP" % ("s" if len(lep) > 1 else "", " e ".join(lep))
    m = re.search(r"\bART(?:IGO)?\.?\s*(\d+)", t)
    if not m or (m.group(1) == "60" and "FULCRO" in t[max(0, m.start() - 20):m.start()]):
        m = re.search(r"INFRING\w*\s*(?:EM TESE)?\s*:?\s*O?\s*ART(?:IGO)?\.?\s*(\d+)", t) or (m if m and m.group(1) != "60" else None)
    if not m:
        return ""
    resto = t[m.end():]
    lei = re.search(r"RIBUP|REGIMENTO|DECRETO|\bLEP\b|7\.?210|LEI DE EXECU", resto)
    inc = incisos(m.group(1))
    return "art. %s%s %s" % (m.group(1), inc + "," if inc else "", "do RIBUP" if lei and lei.group(0) in ("RIBUP", "REGIMENTO", "DECRETO") else "da LEP")


def _datas_texto(us):
    """Datas citadas no texto (sem acento, maiúsculo): dd/mm/aaaa, dd.mm.aaaa e "13 de outubro de 2014", na ordem."""
    out = []
    for m in re.finditer(r"(\d{2})[/.](\d{2})[/.](\d{4})|(\d{1,2})\s+DE\s+([A-Z]+)\s+DE\s+(\d{4})", us):
        if m.group(1):
            d = _dp("%s.%s.%s" % m.group(1, 2, 3))
        else:
            d = _dp("%02d.%02d.%s" % (int(m.group(4)), MESES[m.group(5)], m.group(6))) if m.group(5) in MESES else None
        if d:
            out.append(d)
    return out


# registro que é o julgamento de uma falta (fichas até ~2021): "foi sancionado", "CONDENADO por unanimidade no Procedimento",
# "foi concluído o PADIC ... pelo cometimento de falta grave", "ciência do resultado", "conclusão: praticou falta grave", regressão
_RE_RESULTADO = (r"SANCIONAD|\bCONDENADO POR\b|FOI CONCLUIDO O PADIC|CONCLUSAO:\s*PRATICOU|CIENTE DO RESULTADO|CIENCIA DO RESULTADO|"
                 r"CIENCIA DA DECISAO/CONCLUSAO|PRATICOU FALTA|IMPUTADO (?:N?O )?COMETIMENTO|COMETEU FALTA|CIENCIA D[AO] (?:DECISAO|PADIC|PROCESSO|SANCAO|CONCLUSAO)|CIENTIFICADO DA CONCLUSAO")
# parecer, resumo da ficha ou decisão judicial (regressão, reconhecimento da falta): não é falta nova - casa com a falta do fato
_RE_NARRATIVA = r"PARECER|EM SUA FICHA CONSTA|CONSTA (?:EM SUA|NA) FICHA|^REGRESSAO DE REGIME|RECONHECO A PRATICA"
# data do fato no registro do resultado
_RE_FATO_RES = (r"(?:NA DATA DE|DATA DOS FATOS,? EM|FATO OCORRIDO (?:NO DIA|EM)|DO FATO OCORRIDO NO DIA|A CONTAR DA DATA DE|A CONTAR DE|"
                r"DATA D[OA] (?:FATO|FALTA|OCORRIDO)\W*(?:OU SEJA\W*)?)\s*(\d{2}/\d{2}/\d{2}(?:\d{2})?)\b")
# não é falta: retorno da conduta depois de cumprida a sanção; aviso do setor de educação
_RE_NAO_FALTA = r"RETORNA (?:AO COMPORTAMENTO|O PARECER|SUA CONDUTA)|^EDUCACAO:"


def cpf_cabecalho(cab):
    """CPF do cabeçalho da ficha, com pontos ("060.395.731-55") ou com espaços no lugar deles ("060 395 731-55", "701 076 621 59"):
    guardado no formato com pontos."""
    mcpf = re.search(r"CPF:[ \t]*(\d{3})[. ]?(\d{3})[. ]?(\d{3}) ?[-. ]? ?(\d{2})(?!\d)", cab or "")
    return ("%s.%s.%s-%s" % mcpf.groups()) if mcpf else (re.search(r"CPF:\s*([\d.\-]+\d)", cab or "") or [None, ""])[1]


def filiacao_cabecalho(cab):
    """Filiação do cabeçalho; o "Nº Pront Saúde" pode vir colado ao nome ("...ALBUQUERQUENº Pront Saúde: PDIB - 52.281")."""
    mfi = re.search(r"Filia[çc][ãa]o:\s*(.+?)(?:\s*N[ºo°]\s*Pront|\n|$)", cab or "")
    return mfi.group(1).strip() if mfi else ""


def extrair(caminho):
    with pdfplumber.open(caminho) as pdf:
        pags = [p.extract_text() or "" for p in pdf.pages]
    t = "\n".join(pags)
    if not e_ficha(t):
        raise ValueError("não é uma Ficha Disciplinar do SIAPEN")
    t = _limpar(t)
    f = {"arquivo": caminho, "tipo": "ficha_disciplinar"}
    cab = t.split("HISTÓRICO")[0]
    f["nome"] = (re.search(r"Nome:\s*(.+?)\s+RGI:", cab) or [None, ""])[1].strip() if re.search(r"Nome:\s*(.+?)\s+RGI:", cab) else ""
    f["rgi"] = (re.search(r"RGI:\s*(\d+)", cab) or [None, ""])[1]
    f["cpf"] = cpf_cabecalho(cab)
    f["cpf_em_branco"] = not f["cpf"] and bool(re.search(r"CPF:\s*(?:CIN:|RG:|N/C\b|N[AÃ]O INFORMADO|$)", cab, re.M))
    f["data_nascimento"] = (re.search(r"Data Nascimento:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    # filiação "MÃE \\ PAI" (a mãe vem primeiro no SIAPEN): confronto de identidade com o nome da mãe do RSPE (homônimos)
    f["filiacao"] = filiacao_cabecalho(cab)
    f["nome_mae"] = re.split(r"\s*[\\/|]\s*", f["filiacao"])[0].strip() if f["filiacao"] else ""
    f["artigo"] = (re.search(r"Artigo:\s*(.+)", cab) or [None, ""])[1].strip()
    f["data_prisao"] = (re.search(r"Data Prisão:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    f["condenacao"] = (re.search(r"Condenação:\s*(.+)", cab) or [None, ""])[1].strip()
    f["unidade"] = (re.search(r"Unidade Penal:\s*(.+)", cab) or [None, ""])[1].strip()
    f["data_entrada"] = (re.search(r"Data Entrada:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    # sexo biológico do cadastro do SIAPEN ("M"/"F"): concordância de gênero nos textos (registro do SAP, fundamentações).
    # Sem o campo, a unidade feminina basta; do nome nada se deduz
    msx = re.search(r"Sexo(?: Biol[óo]gico)?:\s*(Masculino|Feminino)", cab, re.I)
    f["sexo"] = msx.group(1)[0].upper() if msx else ("F" if re.search(r"FEMININ", rs._sem_acento(f["unidade"]).upper()) else "")
    mc = re.search(r"HIST[ÓO]RICO\s*-\s*CONDUTA:\s*([^\n]+)", t) or re.search(r"CONDUTA:\s*([A-ZÇÃÕÁÉÍÓÚÂÊÔ/ ]+)", t)
    f["conduta"] = (mc.group(1).strip() if mc else "")
    f["data_impressao"] = (re.search(r"Impresso em (\d{2}/\d{2}/\d{4})", "\n".join(pags)) or [None, ""])[1]
    f["paginas"], f["paginas_sem_texto"] = len(pags), [i + 1 for i, x in enumerate(pags) if len(x.strip()) < 20]
    autos = sorted(set(re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", t)))
    f["autos"] = autos

    # ---- eventos do histórico ----
    hist = t.split("HISTÓRICO", 1)[1] if "HISTÓRICO" in t else t
    partes = RE_LINHA.split(hist)
    eventos = _dividir([{"data": partes[i], "texto": " ".join(partes[i + 1].split())} for i in range(1, len(partes) - 1, 2)])
    eventos = [{"data": e["data"], "d": _dp(e["data"]), "texto": e["texto"]} for e in eventos]
    f["eventos"] = [{"data": e["data"], "texto": e["texto"]} for e in eventos]
    f["versao_leitura"] = VERSAO_LEITURA
    return derivar(f, eventos)


# versão das regras de leitura dos eventos: a ficha guardada na base com versão anterior é relida a partir dos eventos ao abrir
# (9: atestados "PROTOCOLADO ... REMIÇÃO totalizou", dias por extenso, "ias", "228T 76R", substituição "pelo nº X"; faltas antigas)
VERSAO_LEITURA = 9


def _limpar_evento(txt):
    """Tira do texto do evento o cabeçalho de página que a leitura antiga deixou grudado ("RSS (8002969) em: 02/10/2026")."""
    return re.sub(r"\s*\b[A-Z0-9]{2,12}\s*\(\d{5,}\)\s*em:\s*\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?", "", txt or "").strip()


def _dividir(eventos):
    """Lançamentos grudados no texto de outro: data em linha própria seguida de "-" sem texto na mesma linha ("12.12.2017 -\ntexto")
    e sublançamentos das fichas antigas ("... Em 11/03/04 Nesta data iniciou trabalho ..."), cada um com a sua data. Lançamento
    vazio sai; o sublançamento entra na ordem cronológica."""
    out, subs = [], []
    for e in eventos:
        partes, d, ini = [], e["data"], 0
        for m in re.finditer(r"(?:^|(?<=\s))(\d{2}\.\d{2}\.\d{4}) -(?=\s|$)", e["texto"]):
            if m.start() == 0 or re.search(r"\b(?:A|À|ATÉ|ATE|DE|E)\s$", e["texto"][:m.start()], re.I):
                continue  # data no fim de um período ("de 15.09.2022 à 01.02.2023 - ...")
            partes.append((d, e["texto"][ini:m.start()]))
            d, ini = m.group(1), m.end()
        partes.append((d, e["texto"][ini:]))
        for k, (d, t) in enumerate(partes):
            pos = [m for m in re.finditer(r"(?:^|(?<=[\s.;,]))Em (\d{2})/(\d{2})/(\d{2})(?![\d/])", t)]
            pedacos = [(d, t[:pos[0].start()] if pos else t)]
            for j, m in enumerate(pos):
                ds = "%s.%s.%d" % (m.group(1), m.group(2), int(m.group(3)) + (2000 if int(m.group(3)) < 70 else 1900))
                pedacos.append((ds if _dp(ds) else d, t[m.start():pos[j + 1].start() if j + 1 < len(pos) else len(t)]))
            for j, (dd, tt) in enumerate(pedacos):
                tt = tt.strip()
                if tt:
                    ev = dict(e, data=dd, texto=tt) if (k or j) else dict(e, texto=tt)
                    (subs if j else out).append(ev)
    for ev in subs:  # sublançamento: antes do primeiro lançamento posterior a ele
        dv = _dp(ev["data"]) or date.min
        i = next((i for i, x in enumerate(out) if (_dp(x["data"]) or date.min) > dv), len(out))
        out.insert(i, ev)
    return out


def atualizar(f):
    """Ficha guardada com regras de leitura antigas: limpa os eventos e refaz trabalho, atestados, estudo, leitura e faltas
    a partir deles (sem reimportar o PDF). Devolve a própria ficha."""
    if not isinstance(f, dict) or f.get("versao_leitura") == VERSAO_LEITURA or not f.get("eventos"):
        return f
    for e in f["eventos"]:
        e["texto"] = _limpar_evento(e.get("texto"))
    f["eventos"] = _dividir(f["eventos"])
    eventos = [{"data": e["data"], "d": _dp(e["data"]), "texto": e["texto"]} for e in f["eventos"]]
    f["versao_leitura"] = VERSAO_LEITURA
    return derivar(f, eventos)


def derivar(f, eventos):
    """Campos da ficha que vêm dos eventos do histórico (trabalho, atestados, exames, leitura, faltas, estudo)."""

    # ---- trabalho ----
    trabalho, aberto, baixas_orfas = [], None, []
    for e in eventos:
        u = e["texto"].upper()
        m = re.search(r"TRABALHO:\s*INICIOU ATIVIDADE LABORAL,?\s*NO SETOR DE TRABALHO\s*(.+?)(?:,\s*CONFORME|$)", u)
        if m:
            if aberto:
                # um trabalho novo encerra o anterior (a ficha nem sempre registra o "deixa de trabalhar")
                aberto["fim"] = aberto.get("fim") or e["data"]
                aberto.setdefault("motivo_fim", "início de outra atividade")
                trabalho.append(aberto)
            aberto = {"inicio": e["data"], "fim": "", "setor": m.group(1).strip(" ,."), "externo": False}
            continue
        m = re.search(r"TRABALHO:\s*DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.+?)(?:,\s*CONFORME|$)", u)
        if m:
            setor_fim = re.sub(r"\W", "", m.group(1))
            # só encerra o trabalho do mesmo setor (a baixa de um setor antigo não encerra o atual)
            if not (aberto and re.sub(r"\W", "", aberto["setor"].upper())[:12] == setor_fim[:12]):
                # baixa de um setor sem trabalho aberto: a unidade o mantinha alocado sem registrar o início
                ult = [t for t in trabalho if re.sub(r"\W", "", t["setor"].upper())[:12] == setor_fim[:12]]
                baixas_orfas.append({"data": e["data"], "setor": m.group(1).strip(" ,."),
                                     "ultimo_inicio": ult[-1]["inicio"] if ult else "", "ultimo_fim": ult[-1].get("fim", "") if ult else ""})
            if aberto and re.sub(r"\W", "", aberto["setor"].upper())[:12] == setor_fim[:12]:
                aberto["fim"] = e["data"]
                mm = re.search(r"MOTIVO:\s*(.+)$", u)
                aberto["motivo_fim"] = (mm.group(1).strip(" .") if mm else "")
                trabalho.append(aberto)
                aberto = None
            continue
        # desligamento em texto livre, evasão, saída ou transferência de unidade encerram o trabalho em curso
        if aberto and (re.search(r"DESLIGAD[OA]", u) and re.search(r"TRABALHO|LABORA|ATIVIDADE", u)
                       or re.search(r"SA[ÍI]DA DA UNIDADE PENAL|EVAS[ÃA]O|TRANSFER[ÊE]NCIA|FUGA", u)):
            aberto["fim"] = e["data"]
            aberto["motivo_fim"] = ("desligado" if "DESLIGAD" in u else "saída/evasão/transferência")
            trabalho.append(aberto)
            aberto = None
            continue
        if "ATIVIDADE LABORAL EXTERNA" in u and aberto:
            aberto["externo"] = True
            me = re.search(r"EMPRESA\s+(.+?)\s+CONVENIADA", u)
            if me:
                aberto["empresa"] = me.group(1).strip()
    if aberto:
        trabalho.append(aberto)
    # jornada de cada trabalho: a ficha às vezes registra a carga horária ("de segunda a sexta", "12x36") no início
    for t in trabalho:
        ti, tf = _dp(t["inicio"]), _dp(t.get("fim") or "")
        for e in eventos:
            if e["d"] and ti and ti - timedelta(days=3) <= e["d"] <= min(tf or date.max, ti + timedelta(days=30)):
                j = jornada_do_texto(e["texto"])
                if j:
                    t["jornada"] = j
                    break
    f["trabalho"] = trabalho
    f["baixas_sem_inicio"] = baixas_orfas

    # ---- atestados de trabalho (dias trabalhados / remidos): a mesma leitura da conciliação da remição ----
    import rspe_remicao as rrm
    atest = []
    for a in rrm.atestados(eventos):
        ss = [x for x in a["segs"] if x["ini"] and x["fim"]]
        atest.append({"data": a["emissao"].strftime("%d.%m.%Y"), "numero": a["numero"], "dias_trabalhados": a["trab"] or 0, "dias_remidos": a["rem"] or 0,
                      "periodo_inicio": rrm._f(min(x["ini"] for x in ss)) if ss else "", "periodo_fim": rrm._f(max(x["fim"] for x in ss)) if ss else "",
                      "empresa": ", ".join(dict.fromkeys(x["setor"] for x in a["segs"] if x["setor"])), "autos": a.get("autos", ""),
                      "trechos": [{"setor": x["setor"], "inicio": rrm._f(x["ini"]), "fim": rrm._f(x["fim"])} for x in ss] if len(ss) > 1 else []})
    f["atestados"] = atest
    # ENCCEJA / ENEM: certificado peticionado ou registrado na ficha (remição por aprovação - Res. CNJ 391/2021; LEP, art. 126,
    # e § 5º, +1/3, quando houver conclusão do ensino certificada)
    exames = []
    for e in eventos:
        u = e["texto"].upper()
        mx = re.search(r"\b(ENCCEJA|ENEM)\b\s*(\d{4})?", u)
        if mx and re.search(r"CERTIFICAD|APROVA|PETICION|DECLARA", u):
            # conclusão certificada (art. 9º, XIII, dos Decretos 2024/2025): só o certificado do ENCCEJA; o ENEM não certifica a
            # conclusão desde 2017, e a declaração parcial ou a aprovação por área não é conclusão
            cert = mx.group(1) == "ENCCEJA" and "CERTIFICAD" in u and not re.search(r"PARCIAL|NA AREA|NA ÁREA|POR AREA|POR ÁREA", u)
            exames.append({"exame": mx.group(1) + ((" " + mx.group(2)) if mx.group(2) else ""), "data": e["data"], "certificado": cert})
    f["exames"] = exames
    # relatórios de leitura peticionados (remição pela leitura - Res. CNJ 391/2021, art. 5º: 4 dias por obra, até 12 obras por
    # ano): os meses citados em cada petição
    leituras, cursos_pet = [], []
    for e in eventos:
        u = re.sub(r"\s+", " ", e["texto"].upper())
        us = rs._sem_acento(u)
        if re.search(r"PETICIONAD\w* (?:OS |O )?CURSOS? DE QUALIFICACAO", us):
            mm = re.search(r"REFERENTES? AOS? M[EÊ]S(?:ES)?\s+(.+?)\s+DE\s+(\d{4})", us)
            cursos_pet.append({"data": e["data"], "texto": e["texto"],
                               "meses": ["%02d/%s" % (int(x), mm.group(2)) for x in re.findall(r"\d{1,2}", mm.group(1)) if 1 <= int(x) <= 12] if mm else []})
            continue
        if not re.search(r"RELATORIOS? DE LEITURA|RESENHA|REMICAO P(?:OR|ELA) LEITURA", us):
            continue
        if re.search(r"PARTICIPOU DO PROJETO", us) and not re.search(r"LIVRO|RELATORIO|MES", us):
            continue
        if re.search(r"REPROVAD", us):
            continue  # resenha reprovada: não há remição
        meses = []
        memp = re.search(r"CICLO.*EMPRESTIMO DO LIVRO\D{0,5}(\d{2})/(\d{2})/(\d{4})", us)
        if memp:  # "Ciclo Outubro/ Novembro 2022 - Data do Empréstimo do Livro 07/10/2022": uma obra, no mês do empréstimo
            meses = ["%s/%s" % (memp.group(2), memp.group(3))]
        for g in ([] if memp else re.finditer(r"((?:\d{1,2}\s*(?:,|\bE\b|\bE(?=\d))\s*)*\d{1,2})\s*DE\s+(\d{4})", u)):  # "meses 02,03,04 e 05de 2026", "06 e07"
            meses += ["%02d/%s" % (int(x), g.group(2)) for x in re.findall(r"\d{1,2}", g.group(1)) if 1 <= int(x) <= 12]
        _M = r"(?:JANEIRO|FEVEREIRO|MARCO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)"
        if not meses:  # meses por extenso: "mês de novembro e dezembro de 2022 e março de 2023", "mês de Julho 2022", "Ciclo Outubro/ Novembro 2022"
            for g in re.finditer(r"(?<!\d )(?<!\d DE )((?:" + _M + r"\s*(?:,|\bE\b|/)?\s*)+)\s*(?:DE\s+)?(\d{4})", us):
                meses += ["%02d/%s" % (MESES[x], g.group(2)) for x in re.findall(r"[A-Z]+", g.group(1)) if x in MESES]
        if not meses and e["d"]:  # sem o ano ("referente aos meses: março e abril"): o do lançamento (mês posterior a ele: ano anterior)
            g = re.search(r"\bMES(?:ES)?\b\W*(?:DE\s+)?((?:" + _M + r"\s*(?:,|\bE\b|/)?\s*)+)", us)
            if g:
                meses = ["%02d/%d" % (MESES[x], e["d"].year - (MESES[x] > e["d"].month)) for x in re.findall(r"[A-Z]+", g.group(1)) if x in MESES]
        # obras: o título do livro (um atestado de leitura por obra) ou a lista "LIVROS: A, B E C" / "livros: A; B" (o "e" só separa
        # o último título; com os meses conhecidos, no máximo uma obra por mês)
        ml = re.search(r"LIVROS?:\s*(.+?)(?:;?\s*AUTOS|$)", us)
        obras = 0
        if re.search(r"TITULO DO LIVRO", us):
            obras = 1
        elif ml:
            it = [x for x in re.split(r"[,;]", ml.group(1)) if x.strip()]
            obras = len(it) - 1 + len([x for x in re.split(r"\bE\b", it[-1]) if x.strip()]) if it else 0
            obras = min(obras, len(meses)) if meses else obras
        mof = re.search(r"\bOF\.?\s*N?\S*?\s*(\d+/\d{2,4})", us)  # o mesmo relatório (ofício) lançado de novo: conta uma vez
        ant = next((x for x in leituras if mof and x.get("oficio") == mof.group(1)), None)
        if ant:
            if e["d"] and str(e["d"].year)[-2:] == mof.group(1).split("/")[1][-2:] and (_dp(ant["data"]) or date.min).year != e["d"].year:
                ant.update(data=e["data"], meses=meses, obras=obras, texto=e["texto"])  # fica o lançamento do ano do ofício
            continue
        leituras.append({"data": e["data"], "meses": meses, "obras": obras, "texto": e["texto"], "oficio": mof.group(1) if mof else ""})
    f["leituras"] = leituras
    f["cursos_peticionados"] = cursos_pet
    f["dias_trabalhados_atestados"] = sum(a["dias_trabalhados"] for a in atest)
    f["dias_remidos_atestados"] = round(sum(a["dias_remidos"] for a in atest), 2)

    # ---- faltas disciplinares ----
    faltas, narrativas = [], []

    def _nat(us):
        mn = re.search(r"(?:FALTA|NATUREZA)\W*(?:DISCIPLINAR\W*)?(?:DE\s+NATUREZA\W*)?(GRAVE|MEDIA|LEVE)\b", us)
        return mn.group(1) if mn else ""
    for e in eventos:
        u = e["texto"].upper()
        us = rs._sem_acento(u)
        if "CONSELHO DISCIPLINAR" not in u and "FALTA DISCIPLINAR" not in u and "FALTA GRAVE" not in u and \
                not re.search(r"FALTA (?:DISCIPLINAR )?DE NATUREZA|INSTAURAD\w* (?:A |S )?CDS|SANCIONADO ADMINISTRATIVAMENTE|RECONHECO A PRATICA", us):
            continue
        if re.search(_RE_NARRATIVA, us):
            narrativas.append(e)  # casado com a falta do fato depois de lidas todas
            continue
        if re.search(r"INSTAURAD\w* (?:A |S )?CDS|SANCIONADO ADMINISTRATIVAMENTE", us) and not re.search(r"CONSELHO DISCIPLINAR|REGISTRO DE FALTA", us):
            # CD simplificada (semiaberto): "01-FALTOU AO PERNOITE DO DIA d 02-INSTAURADA CDS Nº n 03-SANCIONADO ADMINISTRATIVAMENTE ..." -
            # falta já julgada; o mesmo fato (ou a mesma CDS) lançado de novo é uma falta só
            ds = [x for x in _datas_texto(us) if x <= (e["d"] or date.max)]
            dfato = ds[0].strftime("%d.%m.%Y") if ds else e["data"]
            ncds = (re.search(r"\bCDS?\s*N\S*\s*(\d+)", us) or [None, ""])[1]
            nat = _nat(us)
            alvo = next((x for x in faltas if _dp(x["data_fato"].replace("/", ".")) == _dp(dfato) or (ncds and x.get("cds") == ncds)), None)
            if alvo is None:
                alvo = {"data_registro": e["data"], "data_fato": dfato, "artigo": _artigo_falta(us), "grave": nat == "GRAVE" or "FALTA GRAVE" in us,
                        "texto": e["texto"], "padic": "", "resultado": "", "cds": ncds}
                faltas.append(alvo)
            elif e["texto"] not in alvo["texto"]:
                alvo["texto"] += " | " + e["texto"]
            alvo["grave"] = alvo["grave"] or nat == "GRAVE" or "FALTA GRAVE" in us
            if nat:
                alvo["natureza"] = nat.lower()
            if re.search(r"FALTA JUSTIFICADA|JUSTIFICADA A FALTA|SENDO SUA FALTA JUSTIFICADA|ACATAD\w* (?:A )?JUSTIFICATIVA|JUSTIFICOU|(?<!NAO )APRESENTOU JUSTIFICATIVA PLAUSIVEL", us):
                # falta justificada na CDS: arquivada (sem efeito)
                alvo["resultado"], alvo["data_resultado"], alvo["resultado_tipo"], alvo["situacao"] = e["texto"], e["data"], "arquivado", "arquivada"
            elif re.search(r"SANCIONAD|REABILITA", us):
                alvo["resultado"], alvo["data_resultado"], alvo["resultado_tipo"], alvo["situacao"] = e["texto"], e["data"], "sancionado", "homologada/punida"
            else:
                alvo.setdefault("situacao", "PADIC instaurado")
            continue
        # "ciência da decisão do processo disciplinar ..., referente a falta disciplinar grave cometida em d" (ficha antiga): resultado
        if (re.search(r"REGISTRO DE FALTA|LAN[ÇC]AMENTO DE FALTA|FALTA GRAVE", us) or re.search(_RE_RESULTADO, us) and re.search(r"FALTA (?:DISCIPLINAR )?(?:DE NATUREZA|GRAVE)|PRATICOU FALTA", us)) \
                and "ARQUIV" not in u and "INSTAURA" not in u and "ISOLADO" not in u:
            if re.search(_RE_NAO_FALTA, us):
                continue  # volta da conduta após a sanção, aviso da escola: não é falta nova
            if re.search(_RE_RESULTADO, us) and (re.search(r"CONSELHO DISCIPLINAR|APLICACAO DE SANCAO", us) or re.search(r"ABSOLVID|EXTINT", us)):
                continue  # resultado no formato do Conselho Disciplinar ou absolvição/extinção: tratado com os andamentos do PADIC, abaixo
            if re.search(_RE_RESULTADO, us):
                # ficha antiga: a ciência do resultado (sanção, condenação no PADIC) vem como registro próprio - é o julgamento de uma
                # falta, não outra falta; casa com a falta do mesmo fato ou vira a falta já julgada
                mf = re.search(_RE_FATO_RES, us) or re.search(r"COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", us)
                dfr = (mf.group(1) if len(mf.group(1)) == 10 else _d(mf.group(1)).strftime("%d/%m/%Y")) if mf and _d(mf.group(1)) else e["data"]
                alvo = next((x for x in faltas if x["data_fato"].replace(".", "/") == dfr.replace(".", "/")), None)
                art = re.search(r"ART\.?\s*(50|52)\b", us)
                nat = _nat(us)
                if alvo is None:
                    alvo = {"data_registro": e["data"], "data_fato": dfr, "artigo": ("art. %s da LEP" % art.group(1)) if art else "",
                            "grave": bool(art) or "FALTA GRAVE" in us or nat == "GRAVE", "texto": e["texto"], "padic": "", "resultado": ""}
                    faltas.append(alvo)
                elif e["texto"] not in alvo["texto"]:
                    alvo["texto"] += " | " + e["texto"]
                alvo["grave"] = alvo["grave"] or "FALTA GRAVE" in us or nat == "GRAVE"
                if nat:
                    alvo["natureza"] = nat.lower()
                alvo["resultado"], alvo["data_resultado"], alvo["resultado_tipo"] = e["texto"], e["data"], "sancionado"
                alvo["situacao"] = "homologada/punida"
                continue
            art = _artigo_falta(u)
            cometida = re.search(r"COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", u)
            dfato = cometida.group(1) if cometida else e["data"]
            grave = bool(re.search(r"\bart\w*\.?\s*5[02]\b", art, re.I)) or "FALTA GRAVE" in u or bool(_arts_lep(u) & {"50", "52"})
            mesma = next((x for x in faltas if x["data_fato"].replace(".", "/") == dfato.replace(".", "/")), None)
            if mesma:
                # o mesmo fato registrado de novo (linha repetida ou outra infração do mesmo dia): uma falta só
                if e["texto"] not in mesma["texto"]:
                    mesma["texto"] += " | " + e["texto"]
                mesma["grave"] = mesma["grave"] or grave
                mesma["artigo"] = mesma.get("artigo") or art
                continue
            faltas.append({"data_registro": e["data"], "data_fato": dfato, "artigo": art, "grave": grave,
                           "texto": e["texto"], "padic": "", "resultado": "",
                           # "RESPONDE PROCESSO - PADIC/...", "RESPONDE CD SIMPLIFICADA/..." ou "RESPONDE /PDIB": o registro já abre o processo
                           "situacao": "PADIC instaurado" if re.search(r"RESPONDE\s*(?:PROCESSO|CD SIMPLIFICADA|/)", u) else "registrada"})
    # isolamento preventivo lançado com a data do fato nula ("FALTA DISCIPLINAR COMETIDA EM 30/12/1899 - RESPONDE PADIC") e sem o
    # registro da falta: a falta é do dia do lançamento, com PADIC
    for e in eventos:
        us = rs._sem_acento(e["texto"]).upper()
        mi = re.search(r"ISOLADO.*LANCAMENTO DE FALTA.*COMETIDA EM\s*\d{2}/\d{2}/(\d{4})", us)
        if not mi or int(mi.group(1)) >= 1950 or not e["d"]:
            continue
        if any(abs(((_dp(x["data_registro"].replace("/", ".")) or date.min) - e["d"]).days) <= 10 for x in faltas):
            continue
        faltas.append({"data_registro": e["data"], "data_fato": e["data"], "artigo": "", "grave": "FALTA GRAVE" in us, "texto": e["texto"], "padic": "",
                       "resultado": "", "situacao": "PADIC instaurado" if re.search(r"RESPONDE\s*(?:PROCESSO|PADIC|CD SIMPLIFICADA|/)", us) else "registrada"})
    # andamento e resultado do PADIC / CD simplificada: casados com a falta pela data do fato ("referente ao fato ocorrido em",
    # "cometida em"), pelo número do PADIC ou, na instauração sem data, pela falta registrada mais próxima; vale o último resultado
    def _nd(x):
        return (x or "").replace(".", "/")

    def _num_padic(u):
        mp = re.search(r"(?:PADIC|CD SIMPLIFICADA)\s*(?:/\s*[\w-]+\s*)?N[ºO°]?\s*([\d][\d./-]+\d)", u)
        return re.sub(r"\D", "", mp.group(1)) if mp else ""
    for e in eventos:
        # erro de digitação na ficha antiga ("tomou ciência da decidsão do Conselho Disciplinar")
        u = re.sub(r"\bDECIDSAO\b", "DECISAO", rs._sem_acento(e["texto"]).upper())
        if not re.search(r"CONSELHO DISCIPLINAR|APLICACAO DE SANCAO", u) or re.search(r"REGISTRO DE FALTA|LANCAMENTO DE FALTA|ISOLADO", u):
            continue
        m = re.search(r"OCORRIDO EM\s*(\d{2}/\d{2}/\d{4})|COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", u)
        npad = _num_padic(u)
        alvo = None
        if m:
            dt = m.group(1) or m.group(2)
            alvo = next((x for x in faltas if _nd(x["data_fato"]) == dt), None) or next((x for x in faltas if _nd(x["data_registro"]) == dt), None)
        if alvo is None and npad:
            alvo = next((x for x in faltas if x.get("padic_num") == npad), None)
        if alvo is None and faltas and re.match(r"CONSELHO DISCIPLINAR:\s*INSTAURACAO", u):
            cand = [x for x in faltas if (x["situacao"] == "registrada" or (x["situacao"] == "PADIC instaurado" and not x["padic"]))
                    and _dp(x["data_registro"]) and _dp(e["data"])
                    and 0 <= (_dp(e["data"]) - _dp(x["data_registro"])).days <= 120]
            alvo = cand[-1] if cand else None
        instaura = bool(re.match(r"CONSELHO DISCIPLINAR:\s*INSTAURACAO", u))
        if not alvo:
            # resultado sem registro da falta na ficha (formato antigo: "tomou ciência da decisão do Conselho Disciplinar ..., sendo
            # imputado o cometimento de falta disciplinar GRAVE, referente ao fato ocorrido em d"): vira a falta já julgada
            if instaura or not re.search(r"CIENCIA D[OA] (?:RESULTADO|DECISAO)|CONCLUSO|DECISAO DO CONSELHO", u) or \
                    not re.search(r"SANCIONAD|COMETEU FALTA|IMPUTADO (?:N?O )?COMETIMENTO|PROPOSTA DE REGRESSAO", u) or re.search(r"ABSOLVID|EXTINT|ARQUIVAD|SANCIONADO PREVENTIVAMENTE|AGUARDA", u):
                continue
            mf = re.search(_RE_FATO_RES, u)
            dt = (m.group(1) or m.group(2)) if m else (mf.group(1) if mf and len(mf.group(1)) == 10 else e["data"])
            alvo = {"data_registro": e["data"], "data_fato": dt, "artigo": _artigo_falta(u), "grave": "FALTA GRAVE" in u or _nat(u) == "GRAVE",
                    "texto": e["texto"], "padic": "", "resultado": "", "situacao": "registrada"}
            faltas.append(alvo)
        if npad:
            alvo["padic_num"] = npad
        if instaura:
            if alvo["situacao"] == "registrada":
                alvo["situacao"] = "PADIC instaurado"
            mp = re.search(r"(?:PADIC|CD SIMPLIFICADA)\s*(?:/\s*[\w-]+\s*)?N[ºO°]?\s*([\d./-]+)", u)
            if mp and mp.group(1).strip("./-"):
                alvo["padic"] = mp.group(1).strip("./-")
            continue
        if not re.search(r"CIENCIA DO RESULTADO|CONCLUSO|ARQUIVADO|EXTINTO|APLICACAO DE SANCAO|DECISAO DO CONSELHO", u):
            continue
        if re.search(r"ABSOLVID", u):
            tipo = "absolvido"
        elif re.search(r"EXTINT", u):
            tipo = "extinto"
        elif re.search(r"ARQUIVAD", u):
            tipo = "arquivado"
        elif re.search(r"SANCIONAD|SANCAO|COMETEU FALTA|RECONHEC|PUNICAO|HOMOLOG|IMPUTADO (?:N?O )?COMETIMENTO|PROPOSTA DE REGRESSAO", u):
            tipo = "sancionado"
        else:
            continue
        alvo["resultado"], alvo["data_resultado"], alvo["resultado_tipo"] = e["texto"], e["data"], tipo
        # absolvição e extinção do processo contam como a falta arquivada: não produzem efeito
        alvo["situacao"] = "homologada/punida" if tipo == "sancionado" else "arquivada"
        nat = _nat(u)
        if tipo == "sancionado" and nat:
            alvo["natureza"] = nat.lower()
            alvo["grave"] = nat == "GRAVE"  # o Conselho pode desclassificar para média ou leve
    # parecer, resumo e decisão judicial: casam com a falta do fato pela data citada (até 10 dias de diferença: "falta ao pernoite
    # em 20/12" x "evasão em 24/12"); a decisão judicial que reconhece a falta ou regride o regime homologa a falta. Sem falta
    # registrada do fato: a decisão judicial com a data do fato (ou, na regressão por evasão sem data, a evasão registrada na
    # ficha) vira a falta homologada; parecer e resumo ficam fora
    for e in narrativas:
        us = rs._sem_acento(e["texto"]).upper()
        judicial = bool(re.search(r"^REGRESSAO DE REGIME|RECONHECO A PRATICA", us))
        ds = [x for x in _datas_texto(us) if e["d"] and x <= e["d"] - timedelta(days=30)]
        if judicial and not ds and re.search(r"EVADI|EVASAO|FUGA|FUGIU", us) and e["d"]:
            ev_ = [x["d"] for x in eventos if x["d"] and e["d"] - timedelta(days=1095) <= x["d"] < e["d"]
                   and re.search(r"MOTIVO:\s*(?:EVAS|FUGA)|^EVASAO|EVADIU", rs._sem_acento(x["texto"]).upper())]
            ds = ev_[-1:]
        alvo = next((x for d_ in ds for x in faltas if _dp(x["data_fato"].replace("/", ".")) and abs((_dp(x["data_fato"].replace("/", ".")) - d_).days) <= 10), None)
        if alvo is None:
            if not (judicial and ds):
                continue
            art = _artigo_falta(us)
            alvo = {"data_registro": e["data"], "data_fato": ds[0].strftime("%d.%m.%Y"), "artigo": art if re.search(r"\b5[02]\b", art) else "", "grave": True,
                    "texto": e["texto"], "padic": "", "resultado": "", "situacao": "registrada"}
            faltas.append(alvo)
        elif e["texto"] not in alvo["texto"]:
            alvo["texto"] += " | " + e["texto"]
        if judicial and alvo["situacao"] != "arquivada":
            alvo["grave"] = True
            if alvo["situacao"] != "homologada/punida":
                alvo["resultado"], alvo["data_resultado"], alvo["resultado_tipo"], alvo["situacao"] = e["texto"], e["data"], "sancionado", "homologada/punida"
    for x in faltas:  # um formato só (o da ficha) e em ordem cronológica, venha a data do lançamento ou do texto
        x["data_fato"] = (x.get("data_fato") or "").replace("/", ".")
    faltas.sort(key=lambda x: _dp(x["data_fato"]) or _dp(x.get("data_registro") or "") or date.min)
    f["faltas"] = faltas

    # ---- outros marcos relevantes ----
    f["regressoes"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"REGRESS", e["texto"], re.I)]
    f["restabelecimentos"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"RESTABELEC", e["texto"], re.I)]
    f["recusa_trabalho"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"RECUSOU VAGA|RECUSA DE TRABALHO", e["texto"], re.I)]
    f["isolamentos"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"ISOLADO|ISOLAMENTO|CELA DISCIPLINAR", e["texto"], re.I)]
    f["estudo"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"ESTUD|LEITURA|CURSO|ESCOLA", e["texto"], re.I) and "TRABALHO" not in e["texto"].upper()]
    f["estudos"] = _estudos(eventos)
    return f


# ---------------------------------------------------------------- confronto com o RSPE

def _itens_conciliacao(C):
    """Itens da Auditoria a partir da conciliação atestado x remição: pendências acionáveis e alertas de qualidade."""
    out = []
    for p_ in C["pendencias"]:
        if p_["status"] == "NAO_LANCADO":
            out.append({"nivel": "alerta", "titulo": "Atestado emitido não lançado: " + p_["texto"].replace("Atestado ", "nº ", 1),
                        "detalhe": "A ficha registra o atestado, e o RSPE não tem remição correspondente (nem pelo número, nem pelos dias). "
                                   "Verificar o peticionamento no SEEU; se não foi peticionado, peticionar e requerer a remição.",
                        "fundamento": "LEP, art. 126, § 1º, II, e § 8º.", "tipo": "remicao-nao-lancada"})
        elif p_["status"] == "SEM_ATESTADO":
            out.append({"nivel": "verificar", "titulo": "Trabalho sem atestado nem remição: " + p_["texto"],
                        "detalhe": "Estimativa em dias de segunda a sábado (LEP, art. 33), só onde não há atestado nem remição. Pedir o atestado à unidade "
                                   "e requerer a remição dos dias efetivamente trabalhados.", "fundamento": "LEP, arts. 126 e 129.", "tipo": "remicao-sem-atestado"})
        elif p_["status"] == "LACUNA":
            out.append({"nivel": "verificar", "titulo": "Lacuna na conciliação da remição: " + p_["texto"],
                        "detalhe": "Intervalo sem vínculo de trabalho comprovado entre períodos atestados: verificar se houve trabalho no período.",
                        "fundamento": "LEP, arts. 126 e 129.", "tipo": "remicao-lacuna"})
        elif p_["status"] == "DIVERGENCIA":
            out.append({"nivel": "alerta", "titulo": "Divergência de dias na remição: " + p_["texto"],
                        "detalhe": "Os dias do atestado e os da remição do RSPE diferem além do truncamento da fração: " + p_["acao"] + ".",
                        "fundamento": "LEP, art. 126, § 1º, II.", "tipo": "remicao-divergencia"})
    for a in C["alertas"]:
        if a["tipo"] in ("lacuna",):
            continue  # já está nas pendências
        out.append({"nivel": "verificar", "titulo": "Remição - %s: %s" % (a["tipo"], a["texto"][:150]), "detalhe": a["texto"],
                    "fundamento": "LEP, arts. 126 e 129.", "tipo": "remicao-qualidade"})
    return out


def _referencia_remicao(r, C):
    """Remição lançada com referência muito depois do fim do trabalho (em geral, na data da decisão), com um marco no meio:
    o 25/12 de um decreto de indulto/comutação ou uma progressão. Só aí a referência tardia tira os dias da conta; nos
    demais casos ela não muda nada e não gera alerta (fundamentação: remição é declaratória - LEP, art. 126, § 8º, e 128)."""
    out = []
    D = lambda s_: rs.to_date(s_ or "")
    # só decretos com benefício possível: vedado, excluído, fato posterior ou pena máxima acima do limite não mudam com a remição
    _imposs = lambda v: re.match(r"\s*(VEDAD|EXCLU|N[ÃA]O SE APLICA|N[ÃA]O CABE|SEM PENA)", v, re.I) or re.search(
        r"PENA M[ÁA]XIMA EM ABSTRATO SUPERIOR|FATO POSTERIOR", v, re.I)
    anos = sorted({int(m.group(1)) for k in r for m in [re.match(r"(?:indulto|comutacao)_(\d{4})$", k)] if m and r.get(k) and not _imposs(str(r[k]))})
    marcos = [(date(a, 12, 25), "do decreto de 25/12/%d" % a) for a in anos]
    for i in r.get("_incidentes") or []:
        if (i.get("situacao") or "CONCEDIDO") == "CONCEDIDO" and "REGIME" in (i.get("tipo") or "").upper() \
                and "PROGRESS" in (i.get("complemento") or "").upper() and D(i.get("data_referencia")):
            marcos.append((D(i["data_referencia"]), "da progressão de %s (%s)" % (i["data_referencia"], (i.get("complemento") or "").strip())))
    if not marcos:
        return out
    db = D(r.get("data_base_seeu"))
    for a in C.get("atestados") or []:
        x = a.get("remicao")
        segs = [s_ for s_ in a.get("segs") or [] if not s_.get("inferido") and s_.get("ini") and s_.get("fim")]
        if not x or a.get("origem") == "rspe" or not segs or not x.get("ref"):
            continue
        ini_p, fim_p = min(s_["ini"] for s_ in segs), max(s_["fim"] for s_ in segs)
        if (x["ref"] - fim_p).days <= 30:
            continue
        ms = sorted(m for m in marcos if fim_p < m[0] < x["ref"])
        if not ms:
            continue
        dias = int(x.get("dias") or 0)
        na_dec = x.get("decisao") and abs((x["ref"] - x["decisao"]).days) <= 3
        cautela = ""
        if db and fim_p < db <= x["ref"]:
            cautela = (" Cautela: a data-base atual (%s) fica entre o fim do trabalho e a referência lançada. Retificada a referência, os dias "
                       "passam para antes da data-base e deixam de contar para a próxima progressão: pedir a retificação junto com o "
                       "recálculo do benefício que ela antecipa (o decreto ou a progressão acima), e só se o ganho compensar." % rs.fmt(db))
        out.append({"nivel": "alerta",
                    "titulo": "Remição de %s (atestado %s) lançada em %s%s; o trabalho terminou em %s, antes %s" % (
                        rs.pl(dias, "dia", "dias"), a.get("numero") or "s/n", rs.fmt(x["ref"]), " (data da decisão)" if na_dec else "",
                        rs.fmt(fim_p), " e ".join(m[1] for m in ms)),
                    "detalhe": "Período trabalhado de %s a %s, conforme a ficha; o SEEU lançou os dias remidos com referência em %s. Assim, eles "
                               "ficam fora da pena cumprida na data %s. Pedir a retificação da data de referência para o fim do período "
                               "trabalhado e a reanálise do benefício afetado.%s" % (
                                   rs.fmt(ini_p), rs.fmt(fim_p), rs.fmt(x["ref"]), " e na ".join(m[1] for m in ms), cautela),
                    "fundamento": "LEP, arts. 126, § 8º, e 128 (a remição é pena cumprida e a decisão é declaratória); STF, ARE 1.497.973 AgR/PR.",
                    "tipo": "remicao-referencia-tardia", "ref": rs.fmt(x["ref"])})
    return out


def confrontar(r, f, hoje=None, manuais=None):
    """Compara ficha (f) com o registro do RSPE (r). Devolve lista de itens no formato da auditoria:
    {nivel, titulo, detalhe, fundamento}."""
    hoje = hoje or date.today()
    itens = []
    if not f:
        return itens
    linhas, res = quadro_trabalho(r, f, hoje, manuais)
    C = res.get("conc")
    if C:
        itens.extend(_itens_conciliacao(C))
        itens.extend(_referencia_remicao(r, C))
    else:
        itens.append(_item_rf("verificar", "Remição pelo trabalho: falha na conciliação atestado x remição (%s)" % res.get("conc_erro", "?"),
                              "Conferir os atestados da ficha e as remições do RSPE manualmente.", "LEP, art. 126."))
    # 3b) falta grave anterior registrada na ficha x perda de dias remidos no RSPE (art. 127: sem desconto em duplicidade)
    itens.extend(_falta_anterior_x_perda(r, f))
    # 3c) cumprimento parado no RSPE x custódia na ficha
    itens.extend(_interrupcao_x_ficha(r, f))
    # 3d) progressão, regressão e livramento cumpridos na unidade e ausentes do RSPE
    itens.extend(_regime_x_ficha(r, f))
    # 3e) identidade, prisão, processos, pena, unidade x regime, fuga e conduta
    for fn in (_identidade_x_ficha, _prisao_x_ficha, _processos_x_ficha, _pena_x_ficha, _unidade_x_ficha, _fuga_x_ficha, _conduta_x_ficha):
        try:
            itens.extend(fn(r, f))
        except Exception as e:
            itens.append(_item_rf("verificar", "Ficha x RSPE: falha ao conferir (%s: %s)" % (fn.__name__.strip("_"), e), "", ""))
    # 4) estudo sem remição (a análise da ficha é só de remição: faltas, regime e identidade ficam fora)
    if res["estudo_horas_pend"] >= 12:
        itens.append({"nivel": "verificar",
                      "titulo": "Remição pelo estudo a requerer: ≈ %d h (≈ %s)" % (res["estudo_horas_pend"], rs.pl(res["estudo_dias_pend"], "dia", "dias")),
                      "detalhe": "Matrículas sem remição no RSPE: " + "; ".join(
                          "%s (%s), %s%s" % (e["curso"].title(), unidade_periodo(linha_unidades(f), e["_ini"], e["_fim"] or hoje)[0], _br(e["inicio"]),
                                             (" a " + _br(e["fim"])) if e.get("fim") else " em diante (matrícula ativa)")
                          for e in res["estudos_pendentes"]) +
                                 ". Horas estimadas em 4 h por dia útil (como nas certidões da EJA), sem contar duas vezes matrículas simultâneas. Requerer a certidão de frequência escolar e a remição.",
                      "fundamento": "LEP, art. 126, § 1º, I (1 dia a cada 12 h de frequência, em no mínimo 3 dias), e § 5º (+1/3 na conclusão do ensino)."})
    for it in itens:
        it.pop("detalhe_", None)
        it["origem"] = "ficha"
        it["titulo"], it["detalhe"] = _br(it["titulo"]), _br(it.get("detalhe") or "")
    return itens


def leitura_parcial(f):
    """Leitura da ficha para o registro da importação: (observações, parcial). Campo que o próprio SIAPEN deixa em branco
    (ex.: "CPF:" vazio no cabeçalho) é observação, não leitura parcial."""
    out, parcial = [], False
    sem = f.get("paginas_sem_texto") or []
    if sem:
        out.append("%s sem texto (%s de %d): imagem ou digitalização - o histórico dessas páginas não foi lido; gerar a ficha de novo no SIAPEN" % (
            "página" if len(sem) == 1 else "páginas", ", ".join(map(str, sem[:12])) + ("…" if len(sem) > 12 else ""), f.get("paginas") or 0))
        parcial = True
    if not f.get("cpf") and f.get("cpf_em_branco"):
        out.append("CPF em branco no SIAPEN (não é falha de leitura): o vínculo ao RSPE usa os autos e o nome")
    falta = [n for k, n in (("nome", "nome"), ("cpf", "CPF"), ("nome_mae", "filiação"), ("unidade", "unidade"), ("data_impressao", "data de impressão"))
             if not f.get(k) and not (k == "cpf" and f.get("cpf_em_branco"))]
    if falta:
        out.append("não lido: %s - %s" % (", ".join(falta), "cabeçalho cortado ou fora do layout" if "nome" in falta or "CPF" in falta
                                          else "última página ausente (sem o rodapé 'Impresso em')" if falta == ["data de impressão"] else "campo em branco no SIAPEN ou fora do layout"))
        parcial = True
    evs = f.get("eventos") or []
    if not evs:
        out.append("histórico vazio: nenhum registro datado lido (ficha sem histórico ou texto fora do layout)")
        parcial = True
    else:
        ds = [d for d in (_dp(e.get("data") or "") for e in evs) if d]
        imp = _dp(f.get("data_impressao") or "")
        if len(ds) < len(evs):
            out.append("%d de %d registros do histórico sem data legível" % (len(evs) - len(ds), len(evs)))
            parcial = True
        if imp and ds and (imp - max(ds)).days > 365 * 2:
            out.append("último registro do histórico em %s, mais de 2 anos antes da impressão (%s): conferir se faltam páginas" % (
                max(ds).strftime("%d/%m/%Y"), imp.strftime("%d/%m/%Y")))
    return out, parcial


def custodia_apos(f, d):
    """Pela movimentação da ficha, a pessoa está custodiada depois de d? (True, texto) se a última movimentação posterior é
    entrada/permanência em unidade sem saída em liberdade depois; (False, texto) se a última é saída em liberdade/fuga;
    (None, '') se a ficha não tem registro posterior a d."""
    ev = sorted(((_dp(e["data"]), e["texto"]) for e in f.get("eventos", []) if _dp(e.get("data") or "")), key=lambda x: x[0])
    dep = [(x, t) for x, t in ev if x > d]
    if not dep:
        return None, ""
    livres = [(x, t) for x, t in dep if RE_SAIDA_LIVRE.search(t)]
    entradas = [(x, t) for x, t in dep if re.search(r"ENTRADA NA UNIDADE|DEU ENTRADA", t, re.I)]
    if livres and (not entradas or livres[-1][0] > entradas[-1][0]):
        mm = re.search(r"MOTIVO:\s*([^,]+)", livres[-1][1], re.I)
        return False, "saída em %s (%s)" % (rs.fmt(livres[-1][0]), mm.group(1).strip().lower() if mm else _br(livres[-1][1])[:60])
    un = f.get("unidade") or ""
    if entradas:
        mu = re.search(r"UNIDADE PENAL:\s*([^,]+)", entradas[-1][1], re.I)
        un = (mu.group(1).strip() if mu else un)
        return True, "entrada em %s%s; último registro em %s" % (rs.fmt(entradas[-1][0]), (" - " + un) if un else "", rs.fmt(dep[-1][0]))
    return True, "registros na unidade%s até %s, sem saída em liberdade" % ((" " + un) if un else "", rs.fmt(dep[-1][0]))


RE_ENTRADA = re.compile(r"ENTRADA NA UNIDADE|DEU ENTRADA", re.I)


def reconciliar_eventos(r, f):
    """RSPE x ficha na retomada do cumprimento. Omissão: o último evento do RSPE é uma interrupção (que não é prisão em
    outro processo) e a ficha registra nova entrada no sistema prisional depois dela, sem saída em liberdade posterior -
    o reinício é lançado pela ficha (evento marcado _ficha), e os cálculos passam a considerar a custódia. Divergência:
    reinício no RSPE posterior à entrada vinda de fora registrada na ficha - devolve o aviso (não altera o RSPE).
    Altera r no lugar; devolve [(tipo, dados)] para a Auditoria."""
    r["_eventos"] = [e for e in r.get("_eventos", []) if not e.get("_ficha")]
    r.pop("_custodia_ficha", None); r.pop("_reconc_ficha", None)
    if not f:
        return []
    ev = sorted(((_dp(e["data"]), e["texto"]) for e in f.get("eventos", []) if _dp(e.get("data") or "")), key=lambda x: x[0])
    if not ev:
        return []
    evs = sorted((e for e in r["_eventos"] if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    avisos = []
    # divergência: interrupção seguida de reinício no RSPE, com entrada vinda de fora na ficha antes do reinício
    for i, e in enumerate(evs[:-1]):
        if "INTERRUP" not in (e.get("tipo") or "").upper():
            continue
        d, g1 = rs.to_date(e["data"]), rs.to_date(evs[i + 1]["data"])
        # só a entrada depois da última soltura antes do reinício: com saída em liberdade no meio, a custódia não é contínua
        _sol = max((x for x, t in ev if d < x < g1 and RE_SAIDA_LIVRE.search(t)), default=None)
        rua = [(x, t) for x, t in ev if d < x < g1 - timedelta(days=2) and RE_ENTRADA_RUA.search(t) and not (_sol and x <= _sol)]
        if rua:
            mm = re.search(r"PROCEDENTE:\s*([^,]+)", rua[0][1], re.I)
            avisos.append(("reinicio-divergente", {"interrupcao": d, "reinicio": g1, "entrada": rua[0][0], "origem": mm.group(1).strip() if mm else "",
                                                   "motivo": (e.get("motivo") or "").strip()}))
    # omissão: parado no RSPE, preso segundo a ficha
    if evs and "INTERRUP" in (evs[-1].get("tipo") or "").upper() and not rs.RE_OUTRO_PROC.search(evs[-1].get("motivo") or ""):
        d = rs.to_date(evs[-1]["data"])
        entradas = [(x, t) for x, t in ev if x > d and RE_ENTRADA.search(t)]
        if entradas:
            x, t = entradas[0]
            ok, _ = custodia_apos(f, x - timedelta(days=1))
            # só é retomada se a pessoa esteve fora: entrada vinda da delegacia/audiência de custódia, ou saída em liberdade
            # entre a interrupção e a entrada. Transferência entre unidades = custódia contínua (provável prisão em outro
            # processo): não se lança nada - a Auditoria alerta a contradição
            fora = RE_ENTRADA_RUA.search(t) or any(d - timedelta(days=3) <= y < x and RE_SAIDA_LIVRE.search(u) for y, u in ev)
            if ok and fora:
                mm = re.search(r"PROCEDENTE:\s*([^,]+)", t, re.I)
                rua = bool(RE_ENTRADA_RUA.search(t))
                r["_eventos"].append({"tipo": "REINÍCIO", "motivo": "%s (lançado pela ficha SIAPEN)" % ("RECAPTURA" if rua else "ENTRADA NO SISTEMA PRISIONAL"),
                                      "complemento": "", "data": rs.fmt(x), "data_decisao": "", "data_referencia": "", "processos": "", "_ficha": True})
                r["_eventos"].sort(key=lambda e2: rs.to_date(e2.get("data") or "") or date.min)
                avisos.append(("reinicio-pela-ficha", {"interrupcao": d, "entrada": x, "origem": mm.group(1).strip() if mm else "", "rua": rua,
                                                       "motivo": (evs[-1].get("motivo") or "").strip()}))
    # omissão: nenhum evento de prisão no RSPE, e a ficha registra a entrada no sistema prisional
    if not evs:
        ent = [(x, t) for x, t in ev if RE_ENTRADA.search(t)]
        x0 = _dp(f.get("data_prisao") or "") or (ent[0][0] if ent else None)
        if x0:
            r["_eventos"].append({"tipo": "PRISÃO", "motivo": "ENTRADA NO SISTEMA PRISIONAL (lançada pela ficha SIAPEN)", "complemento": "",
                                  "data": rs.fmt(x0), "data_decisao": "", "data_referencia": "", "processos": "", "_ficha": True})
            avisos.append(("inicio-pela-ficha", {"entrada": x0}))
    # custódia atual segundo a ficha (depois do último evento do RSPE): afasta o "não iniciou o cumprimento" quando a
    # única prisão registrada é a provisória
    evs2 = sorted((e for e in r["_eventos"] if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    r["_custodia_ficha"] = custodia_apos(f, rs.to_date(evs2[-1]["data"]))[0] if evs2 else None
    r["_reconc_ficha"] = avisos
    return avisos


def _sem_fuga_falsa(t):
    """Texto sem o que parece fuga ou soltura e não é: tentativa de fuga, ameaça ("sob pena de evasão imediata"), não retorno do
    hospital/plantão (internação) e saída por alvará de transferência (mudança de regime, sem liberdade)."""
    u = rs._sem_acento(t or "").upper()
    u = re.sub(r"TEN\w*TATIVA\s+(?:DE\s+)?(?:FUGA|EVASAO)|SOB PENA DE (?:EVASAO|FUGA)|MOTIVO:\s*ALVARA DE TRANSFERENCIA", " ", u)
    if re.search(r"HOSPITAL|INTERNAC|INTERNAD|PLANTAO|CONSULTA", u) and not re.search(r"EVADI|\bFUGA\b|EVASAO|FORAGID", u):
        u = u.replace("NAO RETORNOU", " ")
    return u


class _ReFicha:
    """Regex aplicada ao texto da ficha sem as falsas fugas/solturas (_sem_fuga_falsa)."""
    def __init__(self, rx):
        self.rx = rx

    def search(self, t):
        return self.rx.search(_sem_fuga_falsa(t))


RE_FUGA_FICHA = _ReFicha(re.compile(r"\bFUGA\b|EVADIU|EVAS[ÃA]O|FORAGID|N[ÃA]O RETORNOU|EMPREENDEU FUGA", re.I))
# Unidades da AGEPEN/MS (levantamento de set/2026 nas páginas e notícias da AGEPEN e da SEJUSP): padrão do nome -> (regime,
# nome usual). Ordem importa: a primeira que casa decide ("Penitenciária de Regime Fechado da Gameleira" antes do
# "Centro Penal Agroindustrial da Gameleira"; "Regime Semiaberto, Aberto e Assistência ao Albergado" é semiaberto).
# regime: fechado | semiaberto | aberto | monitoramento | provisorio | federal
UNIDADES_MS = [
    (r"MONITORAMENTO", "monitoramento", "Unidade Mista de Monitoramento Virtual Estadual (UMMVE)"),
    (r"PATRONATO", "aberto", "Patronato Penitenciário (regime aberto, livramento, egressos)"),
    (r"ALTERNATIVAS PENAIS|ESCRIT[ÓO]RIO SOCIAL", "aberto", "Central Integrada de Alternativas Penais / Escritório Social"),
    (r"PENITENCI[ÁA]RIA FEDERAL", "federal", "Penitenciária Federal de Campo Grande"),
    (r"(REGIME\s+)?FECHADO DA GAMELEIRA|PENITENCI[ÁA]RIA ESTADUAL MASCULINA DE REGIME FECHADO", "fechado", "Penitenciária Estadual Masculina de Regime Fechado da Gameleira"),
    (r"AGROINDUSTRIAL", "semiaberto", "Centro Penal Agroindustrial da Gameleira (semiaberto masculino)"),
    (r"SEMI[- ]?ABERTO", "semiaberto", "Estabelecimento de regime semiaberto (e aberto/albergado)"),
    (r"COL[ÔO]NIA PENAL", "semiaberto", "Colônia Penal (semiaberto)"),
    (r"ALBERGAD", "aberto", "Casa do Albergado / assistência ao albergado (regime aberto)"),
    (r"AUDI[ÊE]NCIA DE CUST[ÓO]DIA|\bCPAC\b", "provisorio", "Central Provisória de Audiência de Custódia (CPAC)"),
    (r"TRIAGEM", "provisorio", "Centro de Triagem (Anísio Lima / feminino Irmã Irma Zorzi)"),
    (r"TR[ÂA]NSITO|\bPTRAN\b", "provisorio", "Presídio de Trânsito de Campo Grande (PTRAN)"),
    (r"JAIR FERREIRA|\bEPJFC\b", "fechado", "Estabelecimento Penal Jair Ferreira de Carvalho (segurança máxima)"),
    (r"INSTITUTO PENAL|\bIPCG\b", "fechado", "Instituto Penal de Campo Grande"),
    (r"IRM[ÃA] IRMA ZORZI", "fechado", "Estabelecimento Penal Feminino Irmã Irma Zorzi"),
    (r"JONAS GIORDANO", "fechado", "Estabelecimento Penal Feminino Carlos Alberto Jonas Giordano (Corumbá)"),
    (r"RICARDO BRAND[ÃA]O", "fechado", "Estabelecimento Penal Ricardo Brandão (Ponta Porã)"),
    (r"M[ÁA]XIMO ROMERO", "fechado", "Estabelecimento Penal Máximo Romero (Jardim)"),
    (r"PENITENCI[ÁA]RIA ESTADUAL DE DOURADOS|\bPED\b", "fechado", "Penitenciária Estadual de Dourados"),
    (r"SEGURAN[ÇC]A M[ÁA]XIMA", "fechado", "Penitenciária de Segurança Máxima"),
    (r"PENITENCI[ÁA]RIA|PRES[ÍI]DIO|CADEIA|ESTABELECIMENTO PENAL|CENTRO DE DETEN", "fechado", "Estabelecimento de regime fechado"),
]


def classificar_unidade(nome):
    """(regime, nome usual) da unidade prisional de MS pelo nome impresso no SIAPEN; (None, '') se não reconhecida."""
    for pad, reg, rot in UNIDADES_MS:
        if re.search(pad, nome or "", re.I):
            return reg, rot
    return None, ""


def mesma_mae(a, b):
    """Nomes da mãe (já normalizados) compatíveis: o RSPE corta nomes longos ("CARLA FERNANDA DA SILV") e há abreviações
    ("CARLA F. DA SILVA"). Compatíveis quando iguais, quando um é o começo do outro, ou quando o primeiro e o último nome
    conferem (um podendo ser o começo do outro). Ausente em um deles não decide (compatível)."""
    if not a or not b or a == b or a.startswith(b) or b.startswith(a):
        return True
    lig = ("DE", "DA", "DO", "DAS", "DOS", "E")
    ta = [x.strip(".") for x in a.split() if x.strip(".") not in lig]
    tb = [x.strip(".") for x in b.split() if x.strip(".") not in lig]

    def comp(x, y):
        return bool(x and y) and (x == y or (min(len(x), len(y)) >= 3 and (x.startswith(y) or y.startswith(x))))
    if bool(ta and tb) and comp(ta[0], tb[0]) and comp(ta[-1], tb[-1]):
        return True
    # erro de digitação ou ordem trocada ("FIGUEIRREDO", "RUTE"/"RUTH", "SOUSA"/"SOUZA", "NUNES BARBOSA"/"BARBOSA NUNES")
    import difflib
    if sorted(ta) == sorted(tb) or difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= 0.88:
        return True
    return False


def assinatura_ficha(f):
    """Identifica a ficha (nome, CPF e nascimento) para o operador desvinculá-la de um assistido."""
    return "%s|%s|%s" % (" ".join(rs._sem_acento(f.get("nome") or "").upper().split()), re.sub(r"\D", "", f.get("cpf") or ""), f.get("data_nascimento") or "")


def _item_rf(nivel, titulo, detalhe, fundamento):
    return {"nivel": nivel, "titulo": titulo, "detalhe": detalhe, "fundamento": fundamento, "tipo": "rspe-x-ficha"}


def _identidade_x_ficha(r, f):
    """Mesma pessoa? CPF, nome e nascimento da ficha x RSPE (a ficha vinculada pode ser de homônimo ou o cadastro estar errado)."""
    out = []
    c1, c2 = re.sub(r"\D", "", r.get("cpf") or ""), re.sub(r"\D", "", f.get("cpf") or "")
    if len(c1) == 11 and len(c2) == 11 and c1 != c2:
        out.append(_item_rf("alerta", "CPF da ficha (%s) difere do RSPE (%s)" % (f.get("cpf"), r.get("cpf")),
                            "A ficha vinculada pode ser de outra pessoa (homônimo) ou um dos cadastros está errado. Conferir antes de usar os dados da ficha.",
                            "Identificação do apenado (LEP, art. 106)."))
    # CPF e nascimento iguais nos dois: é a mesma pessoa - nome ou mãe diferentes são grafia/cadastro (info, não alerta)
    d1, d2 = rs.to_date(r.get("_nasc_rspe") or ("" if r.get("_nasc_fonte") else r.get("data_nascimento")) or ""), _dp(f.get("data_nascimento") or "")
    mesma = len(c1) == 11 and c1 == c2 and d1 and d1 == d2
    nv = "info" if mesma else "alerta"
    _ck = " CPF e nascimento iguais nos dois cadastros: é a mesma pessoa; a diferença é de grafia ou de cadastro." if mesma else ""
    _n = lambda x: " ".join(rs._sem_acento(x or "").upper().split())
    m1, m2 = _n(r.get("nome_mae")), _n(f.get("nome_mae"))
    # filiação da ficha: "PAI \ MÃE" ou "MÃE \ PAI" (a ordem varia) - compara com cada nome
    m2s = [_n(x) for x in re.split(r"\s*[\\/|]\s*", f.get("filiacao") or "") if x.strip()] or [m2]
    # mesma regra do vínculo: ignora "da/de/dos", nome cortado no fim, abreviação e erro de digitação
    _sem = lambda x: re.fullmatch(r"(NAO )?(INFORMAD[OA]|CONSTA|DECLARAD[OA])|IGNORAD[OA]|DESCONHECID[OA]|N/?I|-+", x or "")
    if m1 and m2 and not _sem(m1) and not _sem(m2) and not any(mesma_mae(m1, x) for x in m2s if x):
        out.append(_item_rf(nv, "Mãe na ficha (%s) difere do RSPE (%s)" % ((f.get("nome_mae") or "").title(), (r.get("nome_mae") or "").title()),
                            "O nome da mãe é o critério para separar homônimos: a ficha vinculada pode ser de outra pessoa. Conferir antes de usar os "
                            "dados da ficha (remição, faltas, custódia) e, se não for desta pessoa, usar \"Desvincular ficha\".%s" % _ck,
                            "Identificação do apenado (LEP, art. 106)."))
    # nome: aceita grafia (Nunes/Nunez, Sousa/Souza) e o nome social ("CAMILA ... - CARLOS ...": qualquer das partes)
    n1 = _n(r.get("nome"))
    n2s = [x for x in (_n(y) for y in re.split(r"\s+-\s+", f.get("nome") or "")) if x]
    if n1 and n2s and not any(mesma_mae(n1, x) for x in n2s):
        out.append(_item_rf(nv, "Nome na ficha (%s) difere do RSPE" % (f.get("nome") or "").title(),
                            "RSPE: %s. Conferir se a ficha é desta pessoa.%s" % ((r.get("nome") or "").title(), _ck), "Identificação do apenado (LEP, art. 106)."))
    if d1 and d2 and d1 != d2:
        # só pesa se a diferença muda algum marco: 18/21 anos no fato, 70 na sentença (CP, arts. 27 e 115), 60/70 nos decretos e hoje
        _id = lambda n, ref: ref.year - n.year - ((ref.month, ref.day) < (n.month, n.day))
        _refs = [(rs.to_date(c.get("data_infracao") or ""), (18, 21)) for c in r.get("_crimes", [])]
        _refs += [(rs.to_date(c.get("data_sentenca") or ""), (70,)) for c in r.get("_crimes", [])]
        _refs += [(x, (60, 70)) for x in list(rs.DECRETOS.values()) + [date(2022, 12, 25), date.today()]]
        muda = any(ref and any((_id(d1, ref) >= k) != (_id(d2, ref) >= k) for k in ks) for ref, ks in _refs)
        it = _item_rf("alerta" if muda else "info", "Nascimento na ficha (%s) difere do RSPE (%s)" % (rs.fmt(d2), rs.fmt(d1)),
                      "A data decide a redução do prazo prescricional (CP, art. 115: menor de 21 no fato, maior de 70 na sentença) e as hipóteses de "
                      "indulto por idade. %s" % ("A diferença muda um desses marcos: conferir no documento de identidade e informar a correta pelo botão Preencher."
                                                 if muda else "A diferença não muda nenhum desses marcos (21 anos no fato, 70 na sentença, 60 e 70 nos decretos e hoje)."),
                      "CP, art. 115; decretos de indulto.")
        it["preencher"] = {"campo": "data_nascimento", "rotulo": "Data de nascimento correta (dd/mm/aaaa)", "tipo": "data"}
        if r.get("_nasc_fonte") == "informada pelo operador":
            # o operador já informou a data correta: o alerta sai da contagem, com o dado usado
            it["auto_baixa"] = {"obs": "Data de nascimento informada pelo operador: %s (RSPE: %s; ficha: %s). Usada nos cálculos." % (
                r.get("data_nascimento") or "", rs.fmt(d1), rs.fmt(d2)), "data": r.get("_nasc_data") or ""}
        out.append(it)
    for it in out:
        if not it.get("preencher"):  # CPF, mãe ou nome diferentes: o operador pode tirar a ficha deste assistido
            it["preencher"] = {"campo": assinatura_ficha(f), "rotulo": "Desvincular ficha", "tipo": "desvincular_ficha"}
    return out


def _prisao_x_ficha(r, f):
    """Data da prisão da ficha em período que o RSPE trata como liberdade: custódia sem cômputo (detração)."""
    x = _dp(f.get("data_prisao") or "")
    evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    if not x or not evs:
        return []
    # prisão anterior a todos os fatos desta execução: é de outro processo e não pode ser detraída (CP, art. 42 - vedada a
    # "conta-corrente" de pena)
    _fatos = [rs.to_date(c.get("data_infracao") or "") for c in r.get("_crimes", [])]
    _fatos = [d for d in _fatos if d]
    if _fatos and x < min(_fatos):
        return []
    per = rs.periodos_custodia(evs)
    if any(a - timedelta(days=2) <= x and (b is None or x < b) for a, b in per):
        return []
    depois = [a for a, _ in per if a > x]
    if not depois:
        return []  # parado no RSPE depois dessa data: tratado na retomada
    s = min(depois)
    if any(x < y < s and RE_SAIDA_LIVRE.search(t) for y, t in ((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])) if y):
        return []  # a ficha registra soltura no intervalo: não é custódia contínua até o início no RSPE
    # o início pode ser o reinício que o programa lançou a partir da ficha (evento _ficha), não um registro do RSPE
    pela_ficha = any(e.get("_ficha") and rs.to_date(e.get("data") or "") == s for e in evs)
    return [_item_rf("alerta", ("Prisão em %s na ficha; cômputo só a partir de %s, reinício lançado pela ficha (%s sem cômputo)" if pela_ficha else
                                "Prisão em %s na ficha; RSPE só registra início em %s (%s sem cômputo)") % (rs.fmt(x), rs.fmt(s), rs.pl((s - x).days, "dia", "dias")),
                     "A ficha registra a prisão em %s; %s trata o período até %s como liberdade. Se a prisão foi por este processo (ou por processo "
                     "unificado), os dias entram como detração e antecipam progressão, livramento e término. Conferir o auto de prisão e pedir a retificação." % (
                         rs.fmt(x), "o cálculo (RSPE com o reinício lançado pelo programa a partir da ficha)" if pela_ficha else "o RSPE", rs.fmt(s)),
                     "CP, art. 42; LEP, art. 111.")]


def _processos_x_ficha(r, f):
    """Processos na ficha que não aparecem no RSPE: condenação não somada, prisão por outro processo, guia pendente."""
    rspe = {rs.chave_processo(c.get("processo_criminal") or "") for c in r.get("_crimes", [])}
    rspe.add(rs.chave_processo(r.get("processo_execucao") or ""))
    for o in r.get("_outras_condenacoes") or []:  # processos das outras execuções da mesma pessoa (mesmo CPF)
        rspe.add(rs.chave_processo(o.get("processo_criminal") or ""))
        rspe.add(rs.chave_processo(o.get("_execucao") or ""))
    for e in r.get("_eventos", []) + r.get("_incidentes", []):
        for p in rs.lista_processos(e.get("processos") or ""):
            rspe.add(rs.chave_processo(p))
    fora = [p for p in f.get("autos") or [] if re.match(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$", p) and rs.chave_processo(p) not in rspe]
    if not fora:
        return []
    return [_item_rf("info", "Processos na ficha que o RSPE não lista: %d" % len(fora),
                     "%s. Podem ser ações penais com condenação ainda não somada a esta execução (guia pendente - LEP, art. 111), prisões por outro "
                     "processo (suspensão) ou inquéritos/preventivas já encerrados. Conferir no SEEU e nos sistemas do TJ se há pena a unificar ou prisão "
                     "que deva ser computada." % "; ".join(fora), "LEP, art. 111; CP, art. 42.")]


def _pena_x_ficha(r, f):
    pf, pr = rs.pena_livre(f.get("condenacao") or ""), rs.pena_para_dias(r.get("pena_total"))
    if not pf or not pr or abs(pf - pr) <= 30:
        return []
    return [_item_rf("verificar", "Pena na ficha (%s) difere da pena total do RSPE (%s)" % ((f.get("condenacao") or "").lower(), rs.dias_para_pena(pr)),
                     "A unidade trabalha com outra pena: guia ou unificação não atualizada em um dos sistemas, ou condenação ainda não somada. "
                     "Conferir a última unificação - a pena usada define benefícios, término e remição informados pela unidade.", "LEP, arts. 66, III, a, 106 e 111.")]


def _unidade_x_ficha(r, f):
    """Regime do RSPE x unidade em que a pessoa está (ficha), pela tabela das unidades da AGEPEN."""
    un, reg = (f.get("unidade") or ""), (r.get("regime_atual") or "").upper()
    if not un or not reg or "EXTIN" in reg:
        return []
    tipo_un, rot = classificar_unidade(un)
    if not tipo_un:
        return []
    desde = (" desde %s" % f["data_entrada"]) if f.get("data_entrada") else ""
    if reg.startswith("FECHADO") and tipo_un in ("semiaberto", "aberto", "monitoramento"):
        return [_item_rf("alerta", "RSPE em regime fechado, mas a ficha indica unidade de %s (%s)" % (tipo_un, un.title()),
                         "Unidade atual%s: %s - %s. Provável progressão não lançada no RSPE (a data-base e as frações seguintes mudam) ou regime "
                         "desatualizado no SEEU: conferir a decisão e pedir a atualização." % (desde, un.title(), rot), "LEP, art. 112.")]
    if (reg.startswith("SEMI") or reg.startswith("ABERTO")) and tipo_un in ("fechado", "provisorio", "federal"):
        evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
        if "SUSPENSA" in (r.get("situacao_cumprimento") or "").upper() or (
                evs and "INTERRUP" in (evs[-1].get("tipo") or "").upper() and rs.RE_OUTRO_PROC.search(evs[-1].get("motivo") or "")):
            return []  # execução suspensa (preso em outro processo): a unidade é a da outra prisão
        # nova prisão lançada pelo programa a partir da ficha (recaptura/reinício): justifica o fechado ou a regressão cautelar
        nova = [e for e in evs if e.get("_ficha")]
        return [_item_rf("verificar" if nova else "alerta", "RSPE em regime %s, mas a ficha indica unidade de regime %s (%s)" % (
                             reg.split(" - ")[0].lower(), "fechado" if tipo_un != "provisorio" else "provisório", un.title()),
                         "Unidade atual%s: %s - %s. Se não houve regressão (nem cautelar) ou nova prisão, a pessoa cumpre em regime mais gravoso que o "
                         "fixado: a falta de vaga não autoriza isso - pedir a transferência ou, na falta de vaga, o regime menos gravoso/monitoramento "
                         "(STF, Súmula Vinculante 56; RE 641.320). Se houve regressão, conferir o lançamento no RSPE.%s" % (
                             desde, un.title(), rot, (" O programa lançou %s pela ficha em %s: a nova prisão pode justificar o fechado ou a regressão "
                                                      "cautelar - conferir." % ((nova[-1].get("motivo") or "o reinício").split(" (")[0].lower(), nova[-1]["data"])) if nova else ""),
                         "STF, Súmula Vinculante 56; LEP, arts. 112 e 118.")]
    if reg.startswith("SEMI") and tipo_un in ("aberto", "monitoramento") or reg.startswith("ABERTO") and tipo_un == "semiaberto":
        return [_item_rf("verificar", "RSPE em regime %s; a ficha indica unidade de %s (%s)" % (reg.split(" - ")[0].lower(), tipo_un, un.title()),
                         "Unidade atual%s: %s - %s. Conferir se houve progressão, regressão ou monitoramento eletrônico não lançado no RSPE." % (desde, un.title(), rot),
                         "LEP, arts. 112, 118 e 146-B.")]
    return []


# registro de volta (recaptura, reapresentação, prisão "(evasão)") que cita a evasão sem ser a fuga
RE_RETORNO_FUGA = re.compile(r"RETORN\w*\s+(D[AE]\s+)?(EVAS|FUGA)|RECAPTURAD|REAPRESENTA|\bPRES[OA]\b|MANDADO\s+(JUDICIAL\s+)?DE\s+PRIS", re.I)
# saída da unidade que não é soltura nem fuga, mas tira a pessoa da custódia registrada (novo delito, decisão judicial)
RE_SAIDA_OUTRA = re.compile(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(NOVO DELITO|DECIS[ÃA]O JUDICIAL)", re.I)


def _fuga_x_ficha(r, f):
    """Fuga/evasão na ficha sem registro no RSPE (falta e interrupção omitidas) e fuga no RSPE sem registro na ficha."""
    out = []
    ev_r = [(rs.to_date(e.get("data") or ""), rs._texto_evento(e)) for e in r.get("_eventos", [])]
    ev_r += [(rs.to_date(i.get("data_referencia") or i.get("data_decisao") or ""), rs._rotulo_incidente(i)) for i in r.get("_incidentes", []) if not i.get("_ficha")]
    fugas_r = [d for d, t in ev_r if d and rs.RE_FUGA_EV.search(t)]
    # o SEEU registra a evasão do semiaberto/monitoramento como interrupção por "descumprimento das condições"
    desc_r = [rs.to_date(e.get("data") or "") for e in r.get("_eventos", []) if "INTERRUP" in (e.get("tipo") or "").upper()
              and re.search(r"DESCUMPRI", (e.get("motivo") or "").upper())]
    evs_r = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    per_r = rs.periodos_custodia(evs_r) if evs_r else []
    ini_r = rs.to_date(evs_r[0]["data"]) if evs_r else None
    ev = sorted(((_dp(e["data"]), e["texto"]) for e in f.get("eventos", []) if _dp(e.get("data") or "")), key=lambda x: x[0])
    fugas_f = [(x, t) for x, t in ev if RE_FUGA_FICHA.search(t) and not re.search(r"ABANDONO D[OE] (SERVI|TRABALHO|CURSO)", t, re.I)]
    vistos = []
    for x, t in fugas_f:
        u = _sem_fuga_falsa(t)
        if RE_RETORNO_FUGA.search(u) and not re.search(r"SA[ÍI]DA DA UNIDADE|EVADIU|EMPREENDEU FUGA|N[ÃA]O RETORNOU", u):
            continue  # volta da evasão (recaptura, reapresentação, prisão), não a fuga
        if ini_r and x < ini_r:
            continue  # anterior ao primeiro evento desta execução: é de outra (a ficha cobre a vida prisional toda)
        if per_r and not any(a - timedelta(days=1) <= x and (b is None or x <= b + timedelta(days=1)) for a, b in per_r):
            continue  # período que o RSPE já trata como liberdade: não há custódia desta execução a interromper
        if any(abs((x - d).days) <= 30 for d in fugas_r) or any(d and abs((x - d).days) <= 3 for d in desc_r) or any(abs((x - y).days) <= 3 for y in vistos):
            continue
        vistos.append(x)
        # a omissão favorece o assistido (sem interrupção nem falta, o período conta como cumprido e a data-base não muda)
        out.append(_item_rf("verificar", "Fuga/evasão em %s registrada na ficha e ausente no RSPE" % rs.fmt(x),
                            "Ficha: %s. O RSPE não registra a interrupção nem a falta. A omissão favorece o assistido (o período conta como pena "
                            "cumprida e a data-base não muda): não há o que pedir; conferir só se o registro é desta execução. Sem PAD e homologação, "
                            "a fuga fica como falta \"A apurar\" (Súmula 533/STJ); decida no item da fuga (Preencher)." % _br(t)[:180], "LEP, arts. 50, II, e 118; CP, art. 113."))
    ini_f = ev[0][0] if ev else None
    for d in fugas_r:
        if ini_f and d > ini_f and not any(abs((x - d).days) <= 30 for x, _ in fugas_f):
            # a ficha cobre a data e não registra saída/fuga: custódia contínua?
            antes = [x for x, _ in ev if d - timedelta(days=90) <= x < d]
            depois = [x for x, _ in ev if d < x <= d + timedelta(days=90)]
            livres = [x for x, t in ev if abs((x - d).days) <= 30 and (RE_SAIDA_LIVRE.search(t) or RE_SAIDA_OUTRA.search(t))]
            # soltura por alvará na mesma data da fuga lançada no RSPE: a saída foi legítima, não fuga
            alvara = [(x, t) for x, t in ev if abs((x - d).days) <= 1 and re.search(r"ALVAR[ÁA] DE SOLTURA|MOTIVO:\s*(ALVAR|SOLTURA)", t, re.I)
                      and not re.search(r"APRESENT", t, re.I)]  # quem se apresenta trazendo o alvará está voltando, não saindo
            if alvara:
                out.append(_item_rf("alerta", "Fuga no RSPE em %s, mas a ficha registra saída por alvará de soltura em %s" % (rs.fmt(d), rs.fmt(alvara[0][0])),
                                    "Ficha: %s. A saída foi por ordem judicial, não fuga: a fuga lançada interrompe o cumprimento, move a data-base da "
                                    "progressão, conta como falta grave (indulto, comutação, remição) e interrompe a prescrição (CP, art. 117, V). Pedir a "
                                    "retificação do evento (soltura, não fuga)." % _br(alvara[0][1])[:180],
                                    "LEP, arts. 50, II, 111 e 118; CP, arts. 113 e 117, V."))
            elif antes and depois and not livres:
                out.append(_item_rf("verificar", "Fuga no RSPE em %s sem registro na ficha" % rs.fmt(d),
                                    "A ficha tem movimentação antes e depois dessa data sem saída, fuga ou evasão. Conferir se o evento do RSPE está correto: fuga "
                                    "lançada por engano interrompe o cumprimento, move a data-base da progressão e pode impedir indulto e comutação (falta grave nos 12 meses anteriores ao decreto).", "LEP, arts. 50, II, e 118."))
    return out


def _conduta_x_ficha(r, f, hoje=None):
    """Conduta má/péssima sem falta nos últimos 12 meses (RSPE nem ficha): a classificação deveria ter sido reabilitada."""
    hoje = hoje or date.today()
    c = (f.get("conduta") or "").upper()
    if not re.search(r"\bM[ÁA]\b|P[ÉE]SSIMA|RUIM", c):
        return []
    # prazo de reabilitação por gravidade da última falta (base jurídica: conduta_reabilitacao_meses; padrão 12 meses)
    try:
        import rspe_regras as _rg
        pz = (_rg.carregar() or {}).get("conduta_reabilitacao_meses") or {}
    except Exception:
        pz = {}
    ult_f = max((x for x in f.get("faltas", []) if x.get("situacao") != "arquivada" and _dp(x.get("data_fato") or x.get("data_registro") or "")),
                key=lambda x: _dp(x.get("data_fato") or x.get("data_registro")), default=None)
    meses = int(pz.get("grave" if (ult_f or {}).get("grave", True) else "leve_media", 12) or 12)
    lim = hoje - timedelta(days=int(round(meses * 365 / 12.0)))
    recente_f = [x for x in f.get("faltas", []) if (_dp(x.get("data_fato") or x.get("data_registro") or "") or date.min) >= lim
                 and x.get("situacao") != "arquivada"]
    recente_r = [t for t, _ in rs.indicios_falta(r.get("_incidentes", []), hoje, dias=(hoje - lim).days, eventos=r.get("_eventos", []))]
    if recente_f or recente_r:
        # falta recente que já gerou regressão: o prazo de reabilitação do RIBUP não se aplica à nova progressão (bis in idem)
        _dfs = [_dp(x.get("data_fato") or x.get("data_registro") or "") for x in recente_f if x.get("grave")]
        _regs = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in r.get("_incidentes", [])
                 if re.search(r"REGRESS", rs._rotulo_incidente(i), re.I) and not rs._negado(i)]
        _com_reg = [d for d in _dfs if d and any(x and d <= x <= d + timedelta(days=180) for x in _regs)]
        if _com_reg:
            return [_item_rf("alerta", "Conduta na ficha: %s - falta grave de %s já gerou regressão" % (c.lower(), rs.fmt(max(_com_reg))),
                             "A falta grave foi punida com a regressão de regime. Para a nova progressão, exigir o prazo de reabilitação do RIBUP "
                             "(Decreto Estadual 12.140/2006, art. 133) é bis in idem; o bom comportamento se readquire pelo art. 112, § 7º, da LEP "
                             "(após 1 ano da falta ou antes, cumprido o requisito temporal).",
                             "LEP, art. 112, §§ 6º e 7º; RIBUP-MS, art. 133; TJMS, 1603197-76.2026 e 1604181-94.2025 (3ª Câm.), 1605442-31.2024 (1ª Câm.).")]
        return []
    return [_item_rf("alerta", "Conduta na ficha: %s, sem falta nos últimos %d meses" % (c.lower(), meses),
                     "Nem o RSPE nem a ficha registram falta de %s até hoje. A classificação da conduta pela unidade deveria ter sido reabilitada "
                     "(RIBUP-MS, Decreto Estadual 12.140/2006, art. 133: falta grave, 12 meses do cumprimento da sanção; nova falta interrompe - art. 136) "
                     "- pedir o atestado de conduta atualizado: ele pesa no requisito subjetivo da progressão e do livramento." % rs.fmt(lim),
                     "LEP, art. 112, §§ 1º e 7º; CP, art. 83, III; RIBUP-MS, arts. 133 e 136.")]


def _regime_x_ficha(r, f):
    """Progressão, regressão e livramento que a ficha registra (cumprimento da decisão na unidade) e o RSPE não traz."""
    out = []
    incs = [i for i in r.get("_incidentes", []) if not i.get("_ficha") and not rs._negado(i)]
    def no_rspe(padrao, x, dias=45):
        for i in incs:
            t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
            if re.search(padrao, t):
                for c in ("data_referencia", "data_decisao"):
                    d = rs.to_date(i.get(c) or "")
                    if d and abs((d - x).days) <= dias:
                        return True
        return False
    def prog_antes(reg_m, x):
        # a ida à unidade costuma vir meses depois da decisão: progressão para o mesmo regime decidida até ~1 ano antes
        # (ou até 45 dias depois) é a mesma
        for i in incs:
            t = rs._sem_acento(((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()).replace("-", "").replace(" ", "")
            if "PROGRESS" in t and reg_m in t:
                for c in ("data_referencia", "data_decisao"):
                    d = rs.to_date(i.get(c) or "")
                    if d and x - timedelta(days=380) <= d <= x + timedelta(days=45):
                        return True
        return False

    def regime_rspe_em(x):
        # regime em que o RSPE põe a pessoa na data x: o do último incidente de regime (inicial, progressão, regressão,
        # somatório) até essa data
        ult = None
        for i in incs:
            if "REGIME" not in (i.get("tipo") or "").upper() or (i.get("situacao") or "CONCEDIDO") != "CONCEDIDO":
                continue
            d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            reg = re.match(r"\s*(SEMI-?ABERTO|ABERTO|FECHADO)", rs._sem_acento((i.get("complemento") or "").upper()))
            if d and reg and d <= x and (ult is None or d >= ult[0]):
                ult = (d, reg.group(1).replace("-", ""))
        return ult[1] if ult else None

    def evento_rspe(x, dias=10):
        # evento do RSPE na mesma data (reinício, recaptura, início no regime): a transferência acompanha esse evento
        return any(rs.to_date(ev.get("data") or "") and abs((rs.to_date(ev["data"]) - x).days) <= dias
                   for ev in r.get("_eventos", []) if not ev.get("_ficha"))
    vistos = set()
    # progressão/livramento anteriores ao primeiro evento desta execução são de outra (a ficha é da pessoa, não do processo)
    _ini = min((d for d in (rs.to_date(ev.get("data") or "") for ev in r.get("_eventos", [])) if d), default=None)
    # livramento: o RSPE pode registrá-lo só como evento (interrupção - livramento condicional); em período que o RSPE trata
    # como liberdade, a carta de livramento é de outro processo
    _lc_ev = lambda x: any("LIVRAMENTO" in ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper() and rs.to_date(e.get("data") or "")
                           and abs((rs.to_date(e["data"]) - x).days) <= 45 for e in r.get("_eventos", []))
    _evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    _per = rs.periodos_custodia(_evs) if _evs else []
    for e in f.get("eventos", []):
        x, u = _dp(e.get("data") or ""), (e.get("texto") or "").upper()
        if not x or (_ini and x < _ini):
            continue
        m = re.search(r"PROGRESS[ÃA]O DE REGIME PARA O\s+(SEMI[- ]?ABERTO|ABERTO)", u)
        if not m and re.search(r"MOTIVO:\s*PROGRESS", u):
            dest = re.search(r"DESTINO:\s*([^,]+)", u)
            reg_d = classificar_unidade(dest.group(1))[0] if dest else None
            if reg_d in ("semiaberto", "aberto", "monitoramento"):
                m = re.match(r"(.*)", "SEMIABERTO" if reg_d != "aberto" else "ABERTO")
        # a ida para o regime pode estar no RSPE como regime inicial ou início do cumprimento nesse regime (a unidade registra
        # "Motivo: Progressão de Regime" também na saída para o semiaberto de quem começou nele)
        reg_m = re.sub(r"[- ]", "", m.group(1)) if m else ""
        ev_rspe = m and any(re.search(reg_m, rs._sem_acento(((ev.get("tipo") or "") + " " + (ev.get("motivo") or "")).upper()).replace("-", "").replace(" ", ""))
                            and rs.to_date(ev.get("data") or "") and abs((rs.to_date(ev["data"]) - x).days) <= 10 for ev in r.get("_eventos", []))
        # já no regime pelo RSPE (regime inicial ou progressão anterior), progressão decidida até ~1 ano antes ou evento do RSPE
        # na mesma data: a transferência na ficha é o cumprimento do que o RSPE já registra
        _ja = m and (regime_rspe_em(x) in ((reg_m,) if reg_m == "ABERTO" else (reg_m, "ABERTO")) or prog_antes(reg_m, x) or evento_rspe(x))
        if m and ("prog", m.group(1)) not in vistos and not no_rspe(r"PROGRESS", x) and not no_rspe(reg_m.replace("SEMIABERTO", "SEMI-?ABERTO"), x) and not ev_rspe \
                and not _ja:
            vistos.add(("prog", m.group(1)))
            out.append(("Progressão para o %s registrada na ficha em %s e ausente no RSPE" % (m.group(1).lower().replace(" ", ""), rs.fmt(x)),
                        "A ficha registra o cumprimento da progressão (%s). Sem o incidente no RSPE, a data-base e as frações seguintes ficam erradas: "
                        "conferir a decisão e pedir o lançamento no SEEU." % _br(e["texto"])[:160]))
        # saída para o monitoramento eletrônico não é regressão (a unidade registra "Motivo: Regressão de Regime" também na ida
        # ao monitoramento depois de progressão ou reconsideração)
        _dest = re.search(r"DESTINO:\s*([^,]+)", u)
        _dest_brando = bool(_dest) and classificar_unidade(_dest.group(1))[0] == "monitoramento"
        if re.search(r"REGRESS[ÃA]O", u) and "regr" not in vistos and not no_rspe(r"REGRESS", x) and not _dest_brando:
            vistos.add("regr")
            out.append(("Regressão registrada na ficha em %s e ausente no RSPE" % rs.fmt(x),
                        "Ficha: %s. Conferir se houve decisão de regressão (e a falta que a motivou) e o lançamento no SEEU." % _br(e["texto"])[:160]))
        if re.search(r"MOTIVO:\s*LIVRAMENTO CONDICIONAL|BENEFICIADO COM (O )?LIVRAMENTO", u) and "lc" not in vistos and not no_rspe(r"LIVRAMENTO", x) \
                and not _lc_ev(x) and not (_per and not any(a - timedelta(days=1) <= x and (b is None or x <= b + timedelta(days=1)) for a, b in _per)):
            vistos.add("lc")
            out.append(("Livramento condicional registrado na ficha em %s e ausente no RSPE" % rs.fmt(x),
                        "Ficha: %s. Sem o incidente no RSPE, o período de prova não é contado: pedir o lançamento no SEEU." % _br(e["texto"])[:160]))
    return [{"nivel": "alerta", "titulo": t, "detalhe": d, "fundamento": "LEP, arts. 112, 118 e 131.", "tipo": "rspe-x-ficha"} for t, d in out]


def _interrupcao_x_ficha(r, f):
    """RSPE com o cumprimento parado (último evento é interrupção): a ficha explica? Custódia depois da interrupção =
    preso (em outro processo ou sem reinício lançado), não em liberdade nem foragido; saída em liberdade = confirma."""
    out = []
    for tp, x in r.get("_reconc_ficha") or []:
        if tp == "reinicio-pela-ficha":
            out.append({"nivel": "alerta", "titulo": "Reinício omitido no RSPE: lançado pela ficha em %s" % rs.fmt(x["entrada"]),
                        "detalhe": "O RSPE termina na interrupção de %s (%s), sem reinício. A ficha registra entrada%s em %s e custódia desde então. "
                                   "Os cálculos do programa (situação, custódia, prescrição, incisos do indulto) passam a considerar o cumprimento a "
                                   "partir de %s. Pedir a retificação do RSPE (reinício/recaptura) - sem ele, o SEEU não projeta progressão nem livramento." % (
                                       rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta",
                                       (" vinda de " + x["origem"]) if x["origem"] else "", rs.fmt(x["entrada"]), rs.fmt(x["entrada"])),
                        "fundamento": "LEP, arts. 111 e 112; CP, arts. 113 e 117, V.", "tipo": "rspe-x-ficha"})
        elif tp == "inicio-pela-ficha":
            out.append({"nivel": "alerta", "titulo": "RSPE sem evento de prisão: início lançado pela ficha em %s" % rs.fmt(x["entrada"]),
                        "detalhe": "O RSPE não lista eventos de início do cumprimento; a ficha registra a prisão/entrada no sistema prisional em %s. "
                                   "Os cálculos do programa passam a considerar a custódia desde essa data. Conferir a guia e pedir a retificação do RSPE." % rs.fmt(x["entrada"]),
                        "fundamento": "LEP, arts. 105 e 106; CP, art. 42.", "tipo": "rspe-x-ficha"})
        elif tp == "reinicio-divergente":
            dias = (x["reinicio"] - x["entrada"]).days
            out.append({"nivel": "alerta", "titulo": "Retomada divergente: RSPE reinício em %s, ficha entrada em %s" % (rs.fmt(x["reinicio"]), rs.fmt(x["entrada"])),
                        "detalhe": "Depois da interrupção de %s (%s), a ficha registra entrada no sistema prisional%s em %s; o RSPE só reinicia o cumprimento em %s. "
                                   "São %s de custódia fora da conta (pena cumprida, data-base, prescrição): conferir a data da prisão nos autos e pedir a retificação." % (
                                       rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta", (" vinda de " + x["origem"]) if x["origem"] else "",
                                       rs.fmt(x["entrada"]), rs.fmt(x["reinicio"]), rs.pl(dias, "dia", "dias")),
                        "fundamento": "CP, art. 42; LEP, arts. 111 e 112.", "tipo": "rspe-x-ficha"})
    evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    if not evs or "INTERRUP" not in (evs[-1].get("tipo") or "").upper():
        return out
    d = rs.to_date(evs[-1]["data"])
    mot = (evs[-1].get("motivo") or "").strip()
    outro = bool(rs.RE_OUTRO_PROC.search(mot))
    ok, txt = custodia_apos(f, d)
    if ok is None:
        return out if outro else out + [{"nivel": "verificar", "titulo": "Cumprimento interrompido em %s: a ficha não tem registro posterior" % rs.fmt(d),
                                  "detalhe": "Motivo no RSPE: %s. Sem movimentação na ficha depois dessa data, não há como dizer se a pessoa está presa, "
                                             "em liberdade ou foragida: conferir nos autos." % (mot.lower() or "não consta"), "fundamento": "CP, arts. 113 e 116, p. único.", "tipo": "rspe-x-ficha"}]
    if outro and ok:
        return out + [{"nivel": "ok", "titulo": "Suspensão confirmada pela ficha: preso desde a interrupção de %s" % rs.fmt(d),
                 "detalhe": "RSPE: %s. Ficha: %s. Esta execução está suspensa com a pessoa presa - não corre prescrição (CP, art. 116, p. único)." % (mot.lower(), txt),
                 "fundamento": "CP, art. 116, p. único.", "tipo": "rspe-x-ficha"}]
    if outro and not ok:
        return out + [{"nivel": "verificar", "titulo": "Suspensão por prisão em outro processo, mas a ficha registra saída em liberdade",
                 "detalhe": "RSPE: %s em %s. Ficha: %s. Se foi solto no outro processo, esta execução deveria ter sido retomada (reinício): conferir." % (mot.lower(), rs.fmt(d), txt),
                 "fundamento": "LEP, art. 111; CP, art. 116, p. único.", "tipo": "rspe-x-ficha"}]
    if ok:
        return out + [{"nivel": "alerta", "titulo": "RSPE indica pena interrompida em %s, mas a ficha registra custódia" % rs.fmt(d),
                 "detalhe": "Motivo no RSPE: %s. Ficha: %s, sem entrada vinda de fora depois da interrupção (custódia contínua). A pessoa está presa: provável prisão em outro processo (suspensão, sem curso da prescrição - "
                            "CP, art. 116, p. único) ou reinício do cumprimento não lançado. Conferir e pedir a retificação do RSPE (reinício ou "
                            "unificação), que destrava progressão e livramento." % (mot.lower() or "não consta", txt),
                 "fundamento": "LEP, arts. 111 e 112; CP, art. 116, p. único.", "tipo": "rspe-x-ficha"}]
    return out + [{"nivel": "info", "titulo": "Interrupção de %s confirmada pela ficha: %s" % (rs.fmt(d), txt),
             "detalhe": "Motivo no RSPE: %s. A ficha registra a saída do sistema prisional depois da interrupção." % (mot.lower() or "não consta"), "fundamento": "CP, art. 113.", "tipo": "rspe-x-ficha"}]


def _falta_anterior_x_perda(r, f):
    """Falta grave anterior registrada na ficha (e sem homologação no RSPE) x perda de dias remidos por falta posterior:
    pelo art. 127 da LEP, a nova perda não alcança a remição adquirida antes da falta anterior."""
    import rspe_auditoria as ra
    res, faltas_rspe, _ = ra.perdas_por_falta([i for i in r.get("_incidentes", []) if not i.get("_ficha")])
    if not res:
        return []
    ats, incs, _, _e = vincular(r, f)
    itens = []
    fichas = [x for x in f.get("faltas", []) if x.get("grave") and x.get("situacao") == "homologada/punida" and _dp(x.get("data_fato") or "")]
    for x in res:
        fk = x["falta"]
        ant = [fa for fa in fichas if _dp(fa["data_fato"]) < fk - timedelta(days=30)
               and (x["prev"] is None or _dp(fa["data_fato"]) > x["prev"])
               and all(abs((_dp(fa["data_fato"]) - g).days) > 30 for g in faltas_rspe)]
        if not ant:
            continue
        f0 = max(_dp(fa["data_fato"]) for fa in ant)
        fa0 = max(ant, key=lambda fa: _dp(fa["data_fato"]))
        partes, total = [], 0.0
        for q, rem in x["parcelas"]:
            if not rem:
                continue
            inc = next((i for i in incs if i["data"] == rem["data"] and abs(i["dias"] - rem["n"]) < 0.5), None)
            # só é certo quando a remição foi lançada antes da falta anterior: então se refere a trabalho/estudo anterior a ela
            if not inc or max(inc["d"] or date.max, inc["ref"] or date.min) > f0:
                continue
            total += q
            partes.append("%s (remição de %s lançada em %s, antes da falta de %s)" % (rs.pl(q, "dia", "dias"), rs.pl(rem["n"], "dia", "dias"), rem["data"], rs.fmt(f0)))
        if total >= 1:
            itens.append({"nivel": "verificar",
                          "titulo": "Perda de remidos pode alcançar remição anterior à falta de %s (≈ %s)" % (fa0["data_fato"], rs.pl(round(total), "dia", "dias")),
                          "detalhe": "A ficha registra falta grave de %s (%s, decisão do conselho em %s) que não consta homologada no RSPE. Se o juízo a homologou, "
                                     "a contagem da remição recomeçou nessa data e a perda aplicada pela falta de %s não poderia alcançar a remição do trabalho anterior: %s. "
                                     "Conferir a homologação e, se houver, impugnar o cálculo (desconto em duplicidade)." % (
                                         fa0["data_fato"], fa0.get("artigo") or "art. n/i", fa0.get("data_resultado") or "?", rs.fmt(fk), "; ".join(partes)),
                          "fundamento": ra.FUND_127})
    return itens


def resumo(f):
    if not f:
        return ""
    trab = f.get("trabalho", [])
    em = [x for x in trab if not x.get("fim")]
    return "%s, %s remidos · %s" % (
        rs.pl(len(f.get("atestados", [])), "atestado", "atestados"), _dias_txt(f.get("dias_remidos_atestados") or 0),
        ("trabalhando em " + (em[-1].get("empresa") or em[-1].get("setor") or "?") + " desde " + em[-1]["inicio"]) if em else "sem trabalho em curso")


def _fmtn(v):
    v = float(v)
    return ("%d" % v) if abs(v - round(v)) < 0.01 else ("%.2f" % v).replace(".", ",")


# ---------------------------------------------------------------- trabalho por emprego x remição no RSPE

def _norm(t):
    t = (t or "").upper()
    t = re.sub(r"^(PP|CC|A1|R1)\s*-\s*", "", t)
    t = re.sub(r"[-/]?\s*(CPAIG|IPCG|CPAG)\b", "", t)
    return re.sub(r"\W", "", t)


def _nome_emprego(t):
    return t.get("empresa") or re.sub(r"^(PP|CC|A1|R1)\s*-\s*", "", t.get("setor") or "") or "?"


def inicio_execucao(r):
    """Primeira prisão/início de cumprimento registrada no RSPE (antes disso, o trabalho é de outra custódia)."""
    ds = [rs.to_date(e.get("data") or "") for e in r.get("_eventos", []) if re.search(r"PRIS|IN[ÍI]CIO", (e.get("tipo") or "").upper())]
    ds = [d for d in ds if d]
    return min(ds) if ds else None


def remicoes_rspe(r):
    out = []
    for i in r.get("_incidentes", []):
        if rs.e_remicao_concedida(i):  # exclui perda/revogação e remição não concedida ou pendente
            m = re.search(r"([\d.,]+)\s*Dia", i.get("complemento", ""), re.I)
            if m:
                txt = i.get("data_decisao") or i.get("data_referencia") or ""
                out.append({"data": txt, "d": rs.to_date(txt), "ref": rs.to_date(i.get("data_referencia") or "") or rs.to_date(txt),
                            "dias": _num(m.group(1)), "atestados": []})
    out.sort(key=lambda x: x["d"] or date.min)
    return out


def _subconjunto(itens, alvo, valor, maxn=3, tol=1.0, custo=None):
    """Menor subconjunto (até maxn) cuja soma de valor(x) fica a ±tol do alvo.
    Critério: menor custo (ex.: atestados anteriores à execução), depois soma mais exata."""
    from itertools import combinations
    custo = custo or (lambda x: 0)
    melhor = None
    for n in range(1, maxn + 1):
        for comb in combinations(range(len(itens)), n):
            soma = sum(valor(itens[k]) for k in comb)
            dif = abs(soma - alvo)
            if dif <= tol:
                chave = (sum(custo(itens[k]) for k in comb), dif)
                if melhor is None or chave < melhor[0]:
                    melhor = (chave, comb)
        if melhor is not None:
            return [itens[k] for k in melhor[1]]
    return None


HORAS_DIA_ESTUDO = 4  # estimativa: as certidões da EJA atestam 400 h em 100 dias letivos


def _dias_uteis(a, b):
    """Dias letivos estimados: segunda a sexta, sem os feriados (como na estimativa do trabalho)."""
    return dias_trabalho(a, b, "seg-sex")


def jornada_do_texto(txt):
    """Jornada de trabalho registrada na ficha: 'seg-sex', 'seg-sab', '12x36' ou 'todos'; '' se não informada."""
    u = rs._sem_acento(txt or "").upper()
    if re.search(r"12\s*X\s*36", u):
        return "12x36"
    if re.search(r"SEGUNDA\s*(-|A|À)\s*SEXTA|SEG\.?\s*(-|A|À)\s*SEX", u):
        return "seg-sex"
    if re.search(r"SEGUNDA\s*(-|A|À)\s*SABADO|SEG\.?\s*(-|A|À)\s*SAB", u):
        return "seg-sab"
    if re.search(r"SEGUNDA\s*(-|A|À)\s*DOMINGO|TODOS OS DIAS|DIARIAMENTE|INCLUSIVE (AOS )?DOMINGOS", u):
        return "todos"
    return ""


def _pascoa(ano):
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    j, k = c // 4, c % 4
    m = (a + 11 * h) // 319
    r = (2 * e + 2 * j - k - h + m + 32) % 7
    n = (h - m + r + 90) // 25
    p = (h - m + r + n + 19) % 32
    return date(ano, n, p)


def feriados(ano):
    """Feriados nacionais (Lei 662/1949, Lei 6.802/1980, Lei 14.759/2023 - 20/11 desde 2024) e a Sexta-feira Santa."""
    fs = {date(ano, 1, 1), date(ano, 4, 21), date(ano, 5, 1), date(ano, 9, 7), date(ano, 10, 12), date(ano, 11, 2),
          date(ano, 11, 15), date(ano, 12, 25), _pascoa(ano) - timedelta(days=2)}
    if ano >= 2024:
        fs.add(date(ano, 11, 20))
    fs.add(date(ano, 10, 11))  # feriado estadual de Mato Grosso do Sul (Lei estadual 10/1979: criação do Estado)
    # feriados adicionais editáveis na base jurídica (municipais, ponto facultativo reconhecido na unidade): "MM-DD"
    try:
        import rspe_regras as _rg
        for x in ((_rg.carregar() or {}).get("remicao") or {}).get("feriados_adicionais") or []:
            mm, dd = (int(v) for v in str(x).split("-")[:2])
            fs.add(date(ano, mm, dd))
    except Exception:
        pass
    return fs


def dias_trabalho(a, b, jornada=""):
    """Dias de trabalho entre a e b (inclusive) pela jornada: segunda a sexta, segunda a sábado (padrão: LEP, art. 33 -
    descanso aos domingos e feriados), 12x36 (dia sim, dia não) ou todos os dias. Feriados nacionais fora, salvo 12x36/todos."""
    if not a or not b or b < a:
        return 0
    if jornada == "12x36":
        return ((b - a).days + 2) // 2
    if jornada == "todos":
        return (b - a).days + 1
    lim = 5 if jornada == "seg-sex" else 6
    fer = set()
    for y in range(a.year, b.year + 1):
        fer |= feriados(y)
    n, d = 0, a
    while d <= b:
        if d.weekday() < lim and d not in fer:
            n += 1
        d += timedelta(days=1)
    return n


def horas_estudo(p, hoje=None):
    """Horas do período de estudo: as declaradas na ficha ou, se não houver, estimativa de 4 h por dia útil."""
    if p.get("horas"):
        return p["horas"], True
    a, b = _dp(p["inicio"]), _dp(p.get("fim") or "") or (hoje or date.today())
    if not a or b < a:
        return 0, False
    return _dias_uteis(a, b) * HORAS_DIA_ESTUDO, False


def vincular(r, f, hoje=None):
    """Situação de cada atestado e período de estudo da ficha frente às remições do RSPE, sem ligar um ao outro
    (o RSPE não indica a origem da remição). Atestado: _status (sem_remicao | conferir | anterior).
    Estudo: _status (sem_remicao | conferir | anterior | curto | datas)."""
    hoje = hoje or date.today()
    ini = inicio_execucao(r)
    ats = sorted((dict(a) for a in f.get("atestados", [])), key=lambda a: _dp(a["data"]) or date.min)  # cópias: não sujar a ficha
    ests = [dict(e) for e in f.get("estudos", [])]
    incs = remicoes_rspe(r)
    for i in incs:
        i["estudos"] = []
    for a in ats:
        a["_inc"], a["_status"] = [], ""
        a["_fim"] = _d(a.get("periodo_fim") or "") or _dp(a["data"])
    for e in ests:
        e["_inc"], e["_status"] = [], ""
        e["_ini"], e["_fim"] = _dp(e["inicio"]), _dp(e.get("fim") or "")
        e["_horas"], e["_declaradas"] = horas_estudo(e, hoje)
    # O RSPE não diz de onde vem cada remição (trabalho, estudo, ENCCEJA/ENEM, leitura): o programa não liga remição a
    # atestado. Só afirma o que é certo: sem nenhuma remição lançada no RSPE depois do atestado (ou do início do estudo),
    # ele não pode ter sido homologado. Nos demais casos, conferir na decisão.
    def _depois(d0):
        if d0 is None:
            return list(incs)  # data ilegível na ficha: não se afirma a falta de remição (fica "conferir")
        return [i for i in incs if max(i["d"] or date.min, i["ref"] or date.min) >= d0 - timedelta(days=5)]
    for a in ats:
        a["_rem_depois"] = _depois(_dp(a["data"]) or a["_fim"])
        if ini and a["_fim"] and a["_fim"] < ini:
            a["_status"] = "anterior"
        elif not a["_rem_depois"]:
            a["_status"] = "sem_remicao"
        else:
            a["_status"] = "conferir"
    for e in ests:
        e["_rem_depois"] = _depois(e["_ini"])
        if not e["_ini"] or (e.get("fim") and not e["_fim"]) or (e["_fim"] and e["_fim"] < e["_ini"]):
            e["_status"] = "datas"  # início (ou fim) ilegível: não se afirma nem a frequência curta nem a falta de remição
        elif ini and (e["_fim"] or hoje) < ini:
            e["_status"] = "anterior"
        elif ((e["_fim"] or hoje) - (e["_ini"] or hoje)).days + 1 < 3 and e.get("motivo_fim") != "carga horária declarada":  # período inclusivo: 01 a 03 = 3 dias; sem o período, valem as horas declaradas
            e["_status"] = "curto"  # a lei exige as 12 h divididas em pelo menos 3 dias
        elif not e["_fim"] and (hoje - max(e["_ini"], _dp(e.get("ult_registro_edu") or "") or e["_ini"])).days > 365:
            # matrícula aberta há mais de um ano sem cancelamento, renovação nem outro registro escolar: não se estima
            e["_status"] = "duvida"
        elif not e["_rem_depois"]:
            e["_status"] = "sem_remicao"
        else:
            e["_status"] = "conferir"
    return ats, incs, ini, ests


SIGLAS_UNIDADE = [
    (r"INSTITUTO PENAL DE CAMPO GRANDE", "IPCG"), (r"AGROINDUSTRIAL DA GAMELEIRA", "CPAIG"), (r"DOIS IRM", "PDIB"),
    (r"PRES[IÍ]DIO DE TR[AÂ]NSITO", "PTRAN"), (r"JAIR FERREIRA DE CARVALHO", "EPJFC"), (r"MONITORAMENTO", "UMMVE"),
    (r"REGIME ABERTO E CASA ALBERGADO", "EPRACAG"), (r"CUST[OÓ]DIA DE CAMPO GRANDE", "CPAC"), (r"FEMININO", "EPFIIZ"),
    (r"SEMIABERTO FEMININO", "EPFSA"), (r"PENITENCI[AÁ]RIA ESTADUAL DE DOURADOS", "PED"), (r"HARRY AMORIM", "PHAC"),
]


def sigla_unidade(nome):
    u = (nome or "").upper()
    for rx, sg in SIGLAS_UNIDADE:
        if re.search(rx, u):
            return sg
    return (nome or "").strip().title()


def linha_unidades(f):
    """[(data, unidade)] das entradas em unidade penal registradas na ficha."""
    out = []
    for e in f.get("eventos", []):
        m = re.search(r"Entrada na Unidade Penal:\s*(.+?),\s*Procedente", e.get("texto") or "", re.I)
        d = _dp(e.get("data") or "")
        if m and d:
            nome = re.sub(r'["“”]', "", m.group(1)).strip()
            if not out or out[-1][1] != nome or out[-1][0] != d:
                out.append((d, nome))
    out.sort(key=lambda x: x[0])
    return out


def unidade_periodo(tl, a, b):
    """Unidades em que a pessoa estava entre a e b: a última entrada até o início e as entradas no meio
    (transferência no último dia não conta). Devolve (siglas, nomes completos)."""
    if not a or not tl:
        return "—", ""
    b = b or a
    us = []
    for d, u in tl:
        if d <= a:
            us = [u]
        elif d < b and u not in us:
            us.append(u)
    sig = list(dict.fromkeys(sigla_unidade(u) for u in us))
    return (" → ".join(sig) or "—"), " → ".join(dict.fromkeys(us))


def quadro_trabalho(r, f, hoje=None, manuais=None):
    """Uma linha por emprego da ficha: período, atestado que o cobre, remição no RSPE e providência.
    Devolve (linhas, resumo)."""
    hoje = hoje or date.today()
    _ats, incs, ini_exec, ests = vincular(r, f, hoje)
    linhas = []
    tl = linha_unidades(f)
    # relatório de leitura x remição do RSPE: 4 dias por mês/obra peticionado, concedidos depois da petição
    lei_rem, lei_parc = {}, {}
    for parcial in (False, True):
        # 1ª passada: 4 dias por obra exatos; 2ª: remição menor, múltipla de 4 (obra não aprovada): casa e a diferença fica a conferir
        for x in sorted(f.get("leituras") or [], key=lambda x: _dp(x["data"]) or date.min):
            d, n = _dp(x["data"]), len(x.get("meses") or []) or x.get("obras") or 0
            if not (d and n) or x["data"] in lei_rem:
                continue
            c = [i for i in incs if id(i) not in {id(v) for v in lei_rem.values()}
                 and (0 < (i["dias"] or 0) < 4 * n and abs((i["dias"] or 0) / 4.0 - round((i["dias"] or 0) / 4.0)) < 0.01 if parcial
                      else abs((i["dias"] or 0) - 4 * n) < 0.5)
                 and (i["d"] or i["ref"]) and d <= (i["d"] or i["ref"]) <= d + timedelta(days=240)]
            if c:
                lei_rem[x["data"]] = min(c, key=lambda i: i["d"] or i["ref"])
                if parcial:
                    lei_parc[x["data"]] = 4 * n - int(round(lei_rem[x["data"]]["dias"]))
    # estudo (LEP, art. 126, § 1º, I: 1 dia a cada 12 h de frequência, divididas em no mínimo 3 dias)
    pend_est, conf_est, est_duv, est_curso = [], [], [], []
    ult_rem = max((max(i["d"] or date.min, i["ref"] or date.min) for i in incs), default=None)
    for e in ests:
        if e["_status"] == "anterior":
            continue
        fim_e = e["_fim"] or hoje
        du = _dias_uteis(e["_ini"], fim_e) if e["_ini"] else 0
        per = ("%s a %s" % (e["inicio"], e["fim"])) if e["_fim"] else "%s em diante (matrícula ativa)" % e["inicio"]
        per_full = per + ((" · " + e["motivo_fim"]) if e.get("motivo_fim") and e["_fim"] else "")
        horas_txt = ("%d h (declaradas)" % e["_horas"]) if e["_declaradas"] else ("≈ %d h" % e["_horas"])
        L = {"emp": "Estudo · %s%s" % (e["curso"].title().replace("Ead", "EAD").replace("Modulo", "Módulo"), (" (turma %s)" % e["turma"]) if e.get("turma") else ""), "per": _br(per), "per_full": _br(per_full),
             "dias": rs.pl(du, "dia útil", "dias úteis") if du else "—", "at": horas_txt,
             "at_full": ("Carga horária declarada na ficha." if e["_declaradas"] else "Estimativa: %s × %d h por dia (como nas certidões da EJA)." % (rs.pl(du, "dia útil", "dias úteis"), HORAS_DIA_ESTUDO))}
        L["un"], L["un_full"] = unidade_periodo(tl, e["_ini"], e["_fim"] or hoje)
        dias_e = e["_horas"] // 12
        if e["_status"] == "datas":
            L["sit"], L["cor"] = "Conferir datas", "amarelo"
            L["sit_full"] = "Data de início ou de fim do estudo ilegível na ficha (%s): conferir o período na certidão de frequência." % _br(per)
        elif e["_status"] == "curto":
            L["sit"], L["cor"] = "Menos de 3 dias de frequência: as 12 h precisam estar divididas em pelo menos 3 dias (LEP, art. 126, § 1º, I)", "cinza"
        elif e["_status"] == "duvida":
            L["sit"], L["cor"] = "A conferir: matrícula aberta sem registro escolar há mais de um ano", "cinza"
            L["sit_full"] = ("A ficha não registra cancelamento, conclusão nem outra matrícula desde %s: conferir com a unidade se houve "
                             "frequência (o programa não estima horas)." % _br(e.get("ult_registro_edu") or e["inicio"]))
            est_duv.append(e)
        else:
            dentro = next((o for o in ests if o is not e and o["_status"] in ("sem_remicao", "conferir") and o["_ini"] and e["_ini"] and o["_ini"] <= e["_ini"]
                           and (o["_fim"] or hoje) >= (e["_fim"] or hoje) and not e["_declaradas"]), None)
            if dentro:
                L["sit"], L["cor"] = "Já contada na matrícula de %s" % _br(dentro["inicio"]), "cinza"
            elif not e["_fim"] and e["_ini"] and (hoje - e["_ini"]).days <= 90 and not e["_declaradas"]:
                # matrícula aberta há até 90 dias: a certidão do período ainda não é devida (como o trabalho em curso), fora do total
                L["sit"], L["cor"] = "Em curso há até 90 dias (≈ %s): acompanhar" % rs.pl(dias_e, "dia", "dias"), "verde"
                L["sit_full"] = "Matrícula aberta em %s: a certidão de frequência do período ainda não costuma ter sido expedida." % _br(e["inicio"])
                est_curso.append(dict(e, _em_curso=True))
            elif e["_status"] == "sem_remicao":
                L["sit"], L["cor"] = "Requerer remição (≈ %s)" % rs.pl(dias_e, "dia", "dias"), "amarelo"
                L["sit_full"] = "Nenhuma remição lançada no RSPE depois do início do estudo: requerer a certidão de frequência e a remição."
                pend_est.append(e)
            else:
                # parte do estudo posterior à última remição lançada no RSPE: certamente ainda sem remição
                fim_e2 = e["_fim"] or hoje
                if ult_rem and e["_ini"] and not e["_declaradas"] and fim_e2 > ult_rem:
                    ini2 = max(e["_ini"], ult_rem + timedelta(days=1))
                    h2 = _dias_uteis(ini2, fim_e2) * HORAS_DIA_ESTUDO
                    if h2 >= 12 and not e["_fim"] and (fim_e2 - ini2).days <= 90:
                        # matrícula ativa e só até 90 dias depois da última remição: a certidão desse trecho ainda não é devida
                        est_curso.append(dict(e, _ini=ini2, _horas=h2, _em_curso=True))
                        L["sit"], L["cor"] = ("Conferir homologação; após %s, em curso há até 90 dias (≈ %s)" % (rs.fmt(ult_rem), rs.pl(h2 // 12, "dia", "dias"))), "cinza"
                        conf_est.append(e)
                        linhas.append(L)
                        continue
                    if h2 >= 12:
                        pend_est.append(dict(e, _ini=ini2, _horas=h2))
                        L["sit"], L["cor"] = ("Requerer remição após %s (≈ %s)" % (rs.fmt(ult_rem), rs.pl(h2 // 12, "dia", "dias"))), "amarelo"
                        L["sit_full"] = "O período posterior à última remição do RSPE (%s) ainda não pode ter sido homologado; o anterior, conferir na decisão." % rs.fmt(ult_rem)
                        conf_est.append(e)
                        linhas.append(L)
                        continue
                L["sit"], L["cor"] = "Conferir homologação (≈ %s)" % rs.pl(dias_e, "dia", "dias"), "cinza"
                conf_est.append(e)
        linhas.append(L)
    # horas pendentes sem contar duas vezes os dias em que houve duas matrículas ao mesmo tempo
    dias_pend = set()
    horas_decl = 0
    fer_e, anos_e = set(), set()
    for e in pend_est:
        if e["_declaradas"]:
            horas_decl += e["_horas"]
            continue
        d, fim_e = e["_ini"], e["_fim"] or hoje
        while d and d <= fim_e:
            if d.year not in anos_e:
                anos_e.add(d.year)
                fer_e |= feriados(d.year)
            if d.weekday() < 5 and d not in fer_e:
                dias_pend.add(d)
            d += timedelta(days=1)
    horas_pend = horas_decl + len(dias_pend) * HORAS_DIA_ESTUDO
    est_exec = [e for e in ests if e["_status"] in ("sem_remicao", "conferir")]
    res = {"inicio_execucao": ini_exec, "remidos_execucao": 0, "remidos_anteriores": 0,
           "homologados": sum(i["dias"] for i in incs), "remicoes": incs,
           "pendentes": 0, "parciais": 0, "atestados_pendentes": [], "atestados_parciais": [],
           "remidos_estudo": sum(e["_horas"] // 12 for e in est_exec), "estudos_pendentes": pend_est,
           "estudo_horas_pend": horas_pend, "estudo_dias_pend": horas_pend // 12, "estudo_horas_decl": horas_decl,
           "dias_a_atestar": 0, "baixas": 0, "sem_atestado_a_requerer": 0, "sem_n": 0, "diferenca": 0}
    # ---- blocos da tela (o trabalho vem da conciliação, rspe_remicao) ----
    blocos = []
    est = [L for L in linhas if L["emp"].startswith("Estudo")]
    exs = [x for x in f.get("exames", []) if not ini_exec or (_dp(x["data"]) or date.max) >= ini_exec]
    lei = [x for x in f.get("leituras", []) if not ini_exec or (_dp(x["data"]) or date.max) >= ini_exec]
    if est or exs or lei:
        blocos.append({"tipo": "estudo", "titulo": "Estudo", "info": "certidão de frequência", "itens": [
            {"emp": L["emp"].replace("Estudo · ", ""), "un": L.get("un") or "—", "per": "%s · %s" % (L["per"], L["at"]),
             "sit": ("Requerer remição" if L["sit"].startswith("Requerer") else ("Conferir homologação" if L["sit"].startswith("Conferir") else L["sit"]))
                    + (" · verificar acréscimo de 1/3 pela conclusão (LEP, art. 126, § 5º)" if "conclu" in (L.get("per_full") or "").lower() else ""),
             "cor": {"amarelo": "amarelo", "vermelho": "vermelho"}.get(L["cor"], "cinza"),
             "chave": "fd:est:%s:%s" % (_norm(L["emp"]), L["per"])} for L in est] + [
            {"emp": x["exame"], "un": unidade_periodo(tl, _dp(x["data"]), _dp(x["data"]))[0], "per": "certificado registrado em %s" % _br(x["data"]),
             "sit": "Conferir homologação · se certificou a conclusão do ensino, verificar o acréscimo de 1/3 (LEP, art. 126, § 5º)", "cor": "cinza",
             "chave": "fd:exa:%s:%s" % (_norm(x["exame"]), x["data"])} for x in exs] + [
            {"emp": "Leitura" + (" (%s)" % ", ".join(x["meses"]) if x["meses"] else ""), "un": unidade_periodo(tl, _dp(x["data"]), _dp(x["data"]))[0],
             "per": "relatórios peticionados em %s%s" % (_br(x["data"]), (" · %s · até %d dias (4 por obra)" % (
                 rs.pl(len(x["meses"]), "mês", "meses"), 4 * len(x["meses"]))) if x["meses"] else ""),
             "sit": ("Remida no RSPE: %s em %s%s" % (rs.pl(round(lei_rem[x["data"]]["dias"]), "dia", "dias"), rs.fmt(lei_rem[x["data"]]["d"] or lei_rem[x["data"]]["ref"]),
                                                    (" · menos que os %d da petição: conferir a decisão (obra não aprovada?)" % (lei_parc[x["data"]] + round(lei_rem[x["data"]]["dias"]))) if x["data"] in lei_parc else "")
                     if x["data"] in lei_rem else
                     "Conferir homologação: sem remição de %s no RSPE após a petição (Res. CNJ 391/2021, art. 5º: 4 dias por obra, até 12 por ano)" % rs.pl(4 * len(x["meses"]), "dia", "dias")
                     if x["meses"] else "Conferir homologação · remição pela leitura (Res. CNJ 391/2021, art. 5º: 4 dias por obra, até 12 por ano)"),
             "cor": "verde" if x["data"] in lei_rem and x["data"] not in lei_parc else "amarelo",
             "chave": "fd:lei:%s" % x["data"]} for x in lei]})
    res["blocos"] = blocos
    # ---- conciliação atestado x remição (rspe_remicao): substitui a parte de trabalho do quadro ----
    try:
        import rspe_remicao as rrm
        C = rrm.conciliar(r, f, hoje, manuais, ini_exec, {(i["d"], i["dias"]) for i in lei_rem.values()})
    except Exception as e:  # a base nunca deixa de abrir: o trabalho fica como falha a conferir
        res["conc"], res["conc_erro"] = None, str(e)
        linhas.append({"emp": "Trabalho", "per": "", "dias": "—", "at": "—", "un": "—", "cor": "amarelo",
                       "sit": "Falha na conciliação da remição (%s): conferir a ficha e o RSPE" % e})
        return linhas, res
    res["conc"] = C
    # unidade de cada atestado da conferência (a do fim do período atestado; sem período, a da emissão)
    _por_id = {a["id"]: a for a in C["atestados"]}
    for t_ in C["tabela"]:
        a_ = _por_id.get(t_["id"])
        fs_ = [s["fim"] for s in (a_ or {}).get("segs", []) if s.get("fim")]
        t_["unidade"] = _unidade_em(tl, max(fs_) if fs_ else (a_ or {}).get("emissao")) if a_ else SEM_UNIDADE
    vivos = [a for a in C["atestados"] if a["status"] != "ANTERIOR"]
    nl = [a for a in vivos if a["status"] == "NAO_LANCADO"]
    sem_p = [p for p in C["pendencias"] if p["status"] == "SEM_ATESTADO"]

    def _compat(a):
        ss = [x for x in a["segs"] if x["ini"]]
        return {"numero": a["numero"], "data": rrm._f(a["emissao"]), "dias_trabalhados": a["trab"] or 0, "dias_remidos": a["rem"] or 0,
                "periodo_inicio": rrm._f(min(x["ini"] for x in ss)) if ss else "", "periodo_fim": rrm._f(max(x["fim"] for x in ss)) if ss else ""}
    res["atestados_pendentes"] = [_compat(a) for a in nl]
    # o mesmo valor da remição detalhada: a parte fora do período já remido e, no atestado sem período, só o possível (teto)
    res["pendentes"] = sum(min(a.get("rem_pend", a["rem"]) or 0, a["teto"] if a.get("teto") is not None else float("inf")) for a in nl)
    res["nl_sem_dias"] = sum(1 for a in nl if a["rem"] is None)
    res["remidos_execucao"] = sum(a["rem"] or 0 for a in vivos if a["origem"] != "rspe")
    livres = sum(x["dias"] for x in C["remicoes"] if x["usada"] is None)
    res["diferenca"] = max(0, res["remidos_estudo"] - livres) if res["remidos_estudo"] else 0
    res["sem_n"] = len(sem_p)
    res["em_curso_n"] = len([p for p in C["pendencias"] if p["status"] == "EM_CURSO"])
    res["sem_atestado_a_requerer"] = sum(x["est"] // 3 for x in C["sem_atestado"] if not x.get("duvida") and not (x["em_curso"] and (x["fim"] - x["ini"]).days <= 90))
    res["baixas"] = 0
    # linhas (Excel, relatório e Auditoria): uma por atestado conciliado + as pendências de trabalho
    nov = []
    for t in C["tabela"]:
        nov.append({"emp": "; ".join(dict.fromkeys(x["setor"] for x in t["segs"])), "per": "; ".join(x["per"] for x in t["segs"]), "dias": t["trab"] or "—",
                    "at": "%s · %s remidos" % (t["atestado"], t["rem"]), "sit": t["rot"] + (((" - peticionado em %s: requerer a apreciação" % t["peticionado"]) if t.get("peticionado")
                                                         else " - sem peticionamento na ficha: conferir nos autos (se juntado, requerer a apreciação)") if t["status"] == "NAO_LANCADO" and t["cor"] != "cinza" else ""),
                    "cor": {"verde": "verde", "vermelho": "vermelho", "cinza": "cinza"}.get(t["cor"], "amarelo"), "un": "—"})
    for p_ in C["pendencias"]:
        if p_["status"] in ("SEM_ATESTADO", "LACUNA", "EM_CURSO", "A_CONFERIR"):
            nov.append({"emp": p_["texto"].split(",")[0] if p_["status"] in ("SEM_ATESTADO", "EM_CURSO", "A_CONFERIR") else "Lacuna", "per": p_["texto"], "dias": "—",
                        "at": "sem atestado" if p_["status"] == "SEM_ATESTADO" else "em curso" if p_["status"] == "EM_CURSO" else "a conferir" if p_["status"] == "A_CONFERIR" else "—",
                        "sit": p_["acao"], "cor": p_.get("cor") or "amarelo", "un": "—"})
    linhas = [L for L in linhas if L["emp"].startswith("Estudo")] + nov
    cps = [x for x in f.get("cursos_peticionados") or [] if not ini_exec or (_dp(x["data"]) or date.max) >= ini_exec]
    res["rem_det"] = remicao_detalhada(C, pend_est, lei, lei_rem, res, hoje, tl, cps, est_duv, lei_parc, est_curso)
    return linhas, res


# origens da remição pendente, na ordem do relatório detalhado: (chave, rótulo, providência)
ORIGENS_REMICAO = [
    ("nao_lancado", "Atestado peticionado no SEEU, sem remição no RSPE", "requerer a apreciação (vista às partes e decisão)"),
    ("emitido", "Atestado emitido, sem peticionamento registrado na ficha", "verificar a juntada nos autos e pedir o peticionamento à unidade"),
    ("divergencia", "Atestado com remição menor no RSPE (diferença)", "conferir a decisão e requerer a diferença"),
    ("sem_atestado", "Trabalho sem atestado na ficha nem remição no RSPE", "conferir nos autos se há atestado juntado (o SEEU pode ter atestado não lançado na ficha); se não houver, pedir o atestado à unidade"),
    ("estudo", "Estudo sem remição (certidão a expedir)", "requisitar a certidão de frequência e requerer a remição"),
    ("leitura", "Leitura peticionada sem remição no RSPE", "conferir a homologação da remição pela leitura"),
    ("em_curso", "Trabalho ou estudo em curso há até 90 dias (atestado ou certidão ainda não devidos)", "acompanhar e pedir o atestado ou a certidão ao fim do período"),
    ("a_conferir", "Vínculo sem baixa na ficha (registro duplicado ou baixa esquecida)", "conferir com a unidade se houve trabalho no período"),
]
FORA_DO_TOTAL = ("em_curso", "a_conferir")  # informados à parte: não entram no total a remir


SEM_UNIDADE = "Unidade não identificada na ficha"

# grafias da mesma unidade na ficha (sigla, abreviação, nome antigo): um nome só no relatório por unidade
UNIDADES_CANON = [
    (r"^CT$|CENTRO DE TRIAGEM", "Centro de Triagem Anísio Lima"),
    (r"^CPAIG$|AGROINDUSTRIAL DA GAMELEIRA", "Centro Penal Agroindustrial da Gameleira"),
    (r"GAMELEIRA II\b", "Penitenciária Estadual Masculina de Regime Fechado da Gameleira II"),
    (r"(PENIT\.? EST\.? MASC\.?|PENITENCI[AÁ]RIA ESTADUAL MASCULINA) DE REGIME FECHADO DA GAMELEIRA$",
     "Penitenciária Estadual Masculina de Regime Fechado da Gameleira"),
    (r"^EPJFC$|JAIR FERREIRA DE CARVALHO", "Estabelecimento Penal Jair Ferreira de Carvalho"),
    (r"^EPRACA$|REGIME ABERTO E CASA (DO )?ALBERGADO", "Estabelecimento Penal de Regime Aberto e Casa do Albergado de Campo Grande"),
    (r"^IPCG$|INSTITUTO PENAL DE CAMPO GRANDE", "Instituto Penal de Campo Grande"),
    (r"^PTRAN$|PRES[IÍ]DIO DE TR[AÂ]NSITO", "Presídio de Trânsito de Campo Grande"),
    (r"MONITORAMENTO VIRTUAL", "Unidade Mista de Monitoramento Virtual Estadual de Campo Grande"),
    (r"RICARDO BRAND[AÃ]O", "Unidade Penal Ricardo Brandão"),
    (r"(E\.?P\.?M\.?|ESTABELECIMENTO PENAL MASCULINO) DE (REG\.?|REGIME) SEMIABERTO E ABERTO DE DOURADOS",
     "Estabelecimento Penal Masculino de Regime Semiaberto e Aberto de Dourados"),
    (r"REGIME SEMIABERTO E ABERTO (DE )?AQUIDAUANA", "Estabelecimento Penal de Regime Semiaberto e Aberto de Aquidauana"),
    (r"SEMIABERTO, ABERTO E ASS.* PONTA POR[AÃ]", "Estabelecimento Penal de Regime Semiaberto, Aberto e Assistência ao Albergado de Ponta Porã"),
    (r"SEMIABERTO, ABERTO E ASS.* AMAMBAI", "Estabelecimento Penal de Regime Semiaberto, Aberto e Assistência ao Albergado de Amambai"),
    (r"COL[OÔ]NIA PENAL.*TR[EÊ]S LAGOAS", "Colônia Penal e Industrial de Três Lagoas"),
]


def nome_unidade(nome):
    """Nome da unidade como o relatório mostra: a grafia canônica (UNIDADES_CANON) ou o nome da ficha em caixa de título."""
    u = rs._sem_acento(re.sub(r"\s+", " ", (nome or "").strip())).upper()
    if not u:
        return SEM_UNIDADE
    for rx, nm in UNIDADES_CANON:
        if re.search(rx, u):
            return nm
    lig = ("DE", "DO", "DA", "DOS", "DAS", "E")
    return " ".join(w.lower() if w in lig and k else w.capitalize() for k, w in enumerate((nome or "").strip().upper().split()))


def _segmentos_unidade(tl, a, b):
    """Divide o período a..b pelas entradas em unidade penal da ficha: [(unidade, início, fim)]. Antes da primeira entrada
    registrada (ou sem nenhuma), a unidade fica "não identificada"."""
    if not a:
        return [(SEM_UNIDADE, a, b)]
    b = b or a
    out, atual, ini = [], SEM_UNIDADE, a
    for d, u in tl or []:
        u = nome_unidade(u)
        if d <= a:
            atual = u
        elif d <= b:
            if u != atual:
                out.append((atual, ini, d - timedelta(days=1)))
                atual, ini = u, d
    out.append((atual, ini, b))
    return [x for x in out if x[1] <= x[2]]


def _unidade_em(tl, d):
    u = SEM_UNIDADE
    for e, x in tl or []:
        if d and e <= d:
            u = nome_unidade(x)
    return u


def remicao_detalhada(C, pend_est, lei, lei_rem, res, hoje, tl=None, cursos=None, est_duv=None, lei_parc=None, est_curso=None):
    """Dias a remir por origem e por unidade prisional, com os itens (atestado, período, dias): base do relatório detalhado
    e do pedido de providências. A unidade vem das entradas em unidade penal da ficha; o período que atravessa uma
    transferência é dividido entre as unidades. Atestados: dias do próprio atestado, na unidade em que o período terminou
    (a que emitiu); trabalho sem atestado e em curso: estimativa seg.-sáb. (sem feriados) / 3; estudo: 12 h por dia (horas
    declaradas ou estimadas); leitura: 4 dias por obra, na unidade da petição. Lacunas não têm dias (a conferir)."""
    import rspe_remicao as rrm
    det = {k: {"dias": 0, "itens": [], "por_un": {}} for k, _r, _p in ORIGENS_REMICAO}
    det["lacunas"] = {"dias": 0, "itens": [], "por_un": {}}

    def add(k, item):
        det[k]["itens"].append(item)
        pu = det[k]["por_un"]
        pu[item["unidade"]] = pu.get(item["unidade"], 0) + (item["dias"] or 0)
    for a in (C or {}).get("atestados", []):
        ss = [s for s in a["segs"] if s["ini"]]
        fs = [s["fim"] for s in ss if s["fim"]]
        per = ("%s a %s" % (rrm._f(min(s["ini"] for s in ss)), rrm._f(max(fs)) if fs else "?")) if ss else "período não informado"
        ref = ("Atestado nº %s" % a["numero"]) if a["numero"] else "Atestado s/n"
        setor = "; ".join(dict.fromkeys(s["setor"] for s in a["segs"] if s.get("setor"))) or ""
        un = _unidade_em(tl, max(fs) if fs else a["emissao"])
        pela = " → ".join(dict.fromkeys(u for u, _x, _y in _segmentos_unidade(tl, min(s["ini"] for s in ss), max(fs)))) if ss and fs else un
        base = "%s trabalhados" % a["trab"] if a["trab"] else ""
        if pela != un:
            base = (base + "; " if base else "") + "período em " + pela
        if a["status"] == "NAO_LANCADO" and a["rem"]:
            if "rem_pend" in a:  # cumulativo: a parte já remida por outros atestados não se pede de novo
                base = (base + "; " if base else "") + "%s remidos no atestado, ≈ %s fora do período já remido (%s)" % (
                    _fmtn(a["rem"]), _fmtn(a["rem_pend"]), ", ".join(a["cobertos_por"]))
            dias_ = a.get("rem_pend", a["rem"])
            if a.get("teto") is not None and dias_ > a["teto"]:
                # remidos acima do possível no período (rspe_remicao: plausibilidade): conta só o possível, a conferir no atestado
                base = (base + "; " if base else "") + "%s remidos no atestado, acima do máximo possível no período (≈ %s): conferir o atestado" % (
                    _fmtn(dias_), a["teto"])
                dias_ = a["teto"]
            add("nao_lancado" if a.get("peticionado") else "emitido",
                {"ref": ref, "data": rrm._f(a["emissao"]), "setor": setor, "per": per, "unidade": un,
                 "base": base + (("; " if base else "") + "peticionado em %s" % a["peticionado"] if a.get("peticionado") else ""),
                 "dias": dias_, "estimado": "rem_pend" in a or a.get("teto") is not None, "texto": a.get("texto", "")})
        elif a["status"] == "NAO_LANCADO" and a["rem"] is None:
            # atestado lançado na ficha só com o período, sem os dias: entra na lista (sem dias no total) para conferir o atestado
            add("nao_lancado" if a.get("peticionado") else "emitido",
                {"ref": ref, "data": rrm._f(a["emissao"]), "setor": setor, "per": per, "unidade": un,
                 "base": (base + "; " if base else "") + "a ficha não traz os dias: conferir o atestado" +
                         ("; peticionado em %s" % a["peticionado"] if a.get("peticionado") else ""),
                 "dias": 0, "estimado": False, "sem_dias": True, "texto": a.get("texto", "")})
        elif a["status"] == "DIVERGENCIA" and a["rem"] and a.get("remicao"):
            dif = math.floor(a["rem"] + 1e-9) - int(a["remicao"]["dias"])
            if dif >= 1:
                add("divergencia", {"ref": ref, "data": rrm._f(a["emissao"]), "setor": setor, "per": per, "unidade": un,
                                    "base": "atestado %s × RSPE %s (%s)" % (_fmtn(a["rem"]), int(a["remicao"]["dias"]), rrm._f(a["remicao"]["decisao"])),
                                    "dias": dif, "estimado": False})
    # trabalho sem atestado e em curso: um item por unidade; vínculos simultâneos não somam o mesmo dia duas vezes
    uniao = {"sem_atestado": {}, "em_curso": {}, "a_conferir": {}}

    def _k(x):
        return "a_conferir" if x.get("duvida") else "em_curso" if x["em_curso"] and (x["fim"] - x["ini"]).days <= 90 else "sem_atestado"
    contados = set()  # dias já contados num item anterior (vínculo simultâneo): o item mostra só os dias novos, com aviso
    for x in sorted((C or {}).get("sem_atestado", []), key=lambda x: (["sem_atestado", "em_curso", "a_conferir"].index(_k(x)), x["ini"])):
        k = _k(x)
        fer = set()
        for y in range(x["ini"].year, x["fim"].year + 1):
            fer |= feriados(y)
        aus = {d for c0, c1, _m in x.get("ausencias") or [] for d in rrm._dias_set(c0, c1)}  # isolamento, saída temporária
        for un, a0, b0 in _segmentos_unidade(tl, x["ini"], x["fim"]):
            dias = set()
            d = a0
            while d <= b0:
                if d.weekday() < 6 and d not in fer and d not in aus:
                    dias.add(d)
                d += timedelta(days=1)
            if not dias:
                continue
            uniao[k].setdefault(un, set()).update(dias)
            if len(dias) < 3:
                continue  # sobra de 1 ou 2 dias no corte da transferência: não chega a 1 dia remido (fica só na conta da unidade)
            em = x["em_curso"] and b0 == x["fim"]
            novos = dias - contados
            contados |= dias
            simult = len(dias) - len(novos)
            det[k]["itens"].append({"ref": x["setor"] or "trabalho", "data": "", "setor": x["setor"] or "", "unidade": un,
                                    "per": "%s a %s" % (rrm._f(a0), "hoje (em curso)" if em else rrm._f(b0)),
                                    "base": ("≈ %s (seg.-sáb.)" % rs.pl(len(dias), "dia trabalhado", "dias trabalhados"))
                                            + ((" · %s simultâneos a outro vínculo, já contados" % rs.pl(simult, "dia", "dias")) if simult else "")
                                            + ((" · " + x["duvida"]) if x.get("duvida") else "")
                                            + ((" · " + x["origem"]) if x.get("origem") and a0 == x["ini"] else "")
                                            + ("".join(" · sem %s de %s a %s" % (m_, rrm._f(c0), rrm._f(c1)) for c0, c1, m_ in x.get("ausencias") or [] if a0 <= c1 and c0 <= b0)),
                                    "dias": len(novos) // 3, "estimado": True, "texto": x.get("trecho", "")})
    ja = set().union(*uniao["sem_atestado"].values()) if uniao["sem_atestado"] else set()
    ja2 = ja | (set().union(*uniao["em_curso"].values()) if uniao["em_curso"] else set())
    for k in uniao:
        for un, dias in uniao[k].items():
            if k == "em_curso":
                dias = dias - ja
            elif k == "a_conferir":
                dias = dias - ja2
            det[k]["por_un"][un] = len(dias) // 3
        det[k]["dias"] = sum(det[k]["por_un"].values())
        if sum(i["dias"] for i in det[k]["itens"]) > det[k]["dias"] + 1:
            det[k]["sobreposicao"] = True  # períodos simultâneos: o total é menor que a soma das linhas
    # estudo: horas por unidade (declaradas: proporcionais aos dias úteis de cada unidade); matrícula em curso há até 90 dias à parte
    for e in list(pend_est) + list(est_curso or []):
        ini, fim = e.get("_ini"), e.get("_fim") or hoje
        segs = _segmentos_unidade(tl, ini, fim) if ini else [(SEM_UNIDADE, None, None)]
        du_tot = sum(_dias_uteis(a0, b0) for _u, a0, b0 in segs if a0) or 1
        for un, a0, b0 in segs:
            du = _dias_uteis(a0, b0) if a0 else 0
            h = int(round(e["_horas"] * du / du_tot)) if (e.get("_declaradas") or not a0) and len(segs) > 1 else (e["_horas"] if len(segs) == 1 else du * HORAS_DIA_ESTUDO)
            if h < 12:
                continue
            add("em_curso" if e.get("_em_curso") else "estudo", {"ref": "Estudo · %s" % (e.get("curso") or "").title(), "data": "", "setor": "", "unidade": un,
                           "per": "%s a %s" % (rrm._f(a0), rrm._f(b0) if (b0 != hoje or e.get("_fim")) else "hoje (matrícula ativa)") if a0 else "período não informado",
                           "base": ("%d h declaradas" % h) if e.get("_declaradas") else "≈ %d h" % h, "dias": h // 12, "estimado": not e.get("_declaradas")})
    if det["estudo"]["itens"] and sum(det["estudo"]["por_un"].values()) > (res.get("estudo_dias_pend") or 0) + 1:
        # duas matrículas ao mesmo tempo: o total segue a conta sem dias repetidos, proporcional por unidade
        tot, alvo = sum(det["estudo"]["por_un"].values()), res.get("estudo_dias_pend") or 0
        det["estudo"]["por_un"] = {u: v * alvo // tot for u, v in det["estudo"]["por_un"].items()}
        det["estudo"]["sobreposicao"] = True
    for x in cursos or []:
        # curso de qualificação peticionado no SEEU: a ficha não traz a carga horária - sem dias, para conferir a remição
        det["estudo"]["itens"].append({"ref": "Curso de qualificação peticionado" + (" (%s)" % ", ".join(x["meses"]) if x.get("meses") else ""),
                                       "data": _br(x["data"]), "setor": "", "unidade": _unidade_em(tl, _dp(x["data"])),
                                       "per": "peticionado no SEEU em %s" % _br(x["data"]), "base": "carga horária não informada na ficha",
                                       "dias": 0, "estimado": False})
    det["estudo"]["dias"] = sum(det["estudo"]["por_un"].values())
    det["em_curso"]["dias"] = sum(det["em_curso"]["por_un"].values())  # + matrícula em curso há até 90 dias
    for e in est_duv or []:
        det["a_conferir"]["itens"].append({"ref": "Estudo · %s" % (e.get("curso") or "").title(), "data": "", "setor": "",
                                           "unidade": _unidade_em(tl, e.get("_ini")),
                                           "per": "matrícula desde %s, sem cancelamento" % rrm._f(e["_ini"]) if e.get("_ini") else "período não informado",
                                           "base": "sem registro escolar desde %s: horas não estimadas" % _br(e.get("ult_registro_edu") or e.get("inicio") or ""),
                                           "dias": 0, "estimado": False})
    for x in lei:
        if x["data"] in (lei_parc or {}) and lei_parc[x["data"]] > 0:
            # remida em parte: a diferença (obras da petição sem remição) fica a requerer/conferir
            add("leitura", {"ref": "Leitura" + (" (%s)" % ", ".join(x["meses"]) if x.get("meses") else ""), "data": _br(x["data"]), "setor": "",
                            "unidade": _unidade_em(tl, _dp(x["data"])), "per": "relatórios peticionados em %s" % _br(x["data"]),
                            "base": "remidos %s no RSPE em %s; diferença das obras da petição" % (
                                _fmtn(lei_rem[x["data"]]["dias"]), rs.fmt(lei_rem[x["data"]]["d"] or lei_rem[x["data"]]["ref"])),
                            "dias": lei_parc[x["data"]], "estimado": False})
            continue
        if x["data"] in lei_rem:
            continue
        n = len(x.get("meses") or []) or x.get("obras") or 0
        add("leitura", {"ref": "Leitura" + (" (%s)" % ", ".join(x["meses"]) if x.get("meses") else ""), "data": _br(x["data"]), "setor": "",
                        "unidade": _unidade_em(tl, _dp(x["data"])),
                        "per": "relatórios peticionados em %s" % _br(x["data"]), "base": rs.pl(n, "obra", "obras") if n else "obras não informadas",
                        "dias": 4 * n, "estimado": False})
    det["leitura"]["dias"] = sum(det["leitura"]["por_un"].values())
    det["nao_lancado"]["dias"] = sum(det["nao_lancado"]["por_un"].values())
    det["emitido"]["dias"] = sum(det["emitido"]["por_un"].values())
    det["divergencia"]["dias"] = sum(det["divergencia"]["por_un"].values())
    for p_ in (C or {}).get("pendencias", []):
        if p_["status"] == "LACUNA":
            ds = re.findall(r"\d{2}/\d{2}/\d{4}", p_["texto"])
            add("lacunas", {"ref": "Lacuna", "data": "", "setor": "", "per": p_["texto"], "base": "", "dias": 0, "estimado": False,
                            "unidade": " → ".join(dict.fromkeys(u for u, _a, _b in _segmentos_unidade(tl, _dp(ds[0]), _dp(ds[1])))) if len(ds) >= 2 else SEM_UNIDADE})
    det["total"] = sum(det[k]["dias"] for k, _r, _p in ORIGENS_REMICAO if k not in FORA_DO_TOTAL)
    return det


def _dias_txt(v):
    """'1 dia' / '2,5 dias' / '3 dias'."""
    return "%s %s" % (_fmtn(v), "dia" if v == 1 else "dias")


def _br(txt):
    """dd.mm.aaaa e dd/mm/aa -> dd/mm/aaaa."""
    txt = re.sub(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", r"\1/\2/\3", txt or "")
    return re.sub(r"\b(\d{2})/(\d{2})/(\d{2})\b(?!/|\d)", lambda m: "%s/%s/%s" % (m.group(1), m.group(2), (2000 if int(m.group(3)) < 70 else 1900) + int(m.group(3))), txt)


def fundamentacao_remicao(res):
    """Fundamentação do pedido de remição (atestados sem remição no RSPE e estudo a requerer), no padrão do programa:
    título, fatos e fundamentos em um parágrafo, pedido."""
    ats = res.get("atestados_pendentes") or []
    est_h, est_d = res.get("estudo_horas_pend") or 0, res.get("estudo_dias_pend") or 0
    if not ats and est_h < 12:
        return ""
    par, total = [], 0.0
    if ats:
        total = round(sum(a["dias_remidos"] for a in ats), 2)
        trab = sum(a["dias_trabalhados"] for a in ats)
        lst = "; ".join("nº %s, de %s%s (%s trabalhados)" % ((a.get("numero") or "s/n").split("/ST")[0], _br(a["data"]),
                                                          (", período de %s a %s" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else "",
                                                          _dias_txt(a["dias_trabalhados"])) for a in ats)
        par.append("A ficha disciplinar (SIAPEN) registra %s de trabalho sem remição correspondente no RSPE: %s. %s, à razão de 1 dia de pena "
                   "a cada 3 de trabalho (LEP, art. 126, § 1º, II), correspondem a %s remidos."
                   % (rs.pl(len(ats), "atestado", "atestados"), lst,
                      ("Os %s trabalhados" % _dias_txt(trab)) if len(ats) > 1 else "Os dias trabalhados", _dias_txt(total)))
    if est_h >= 12:
        cursos = "; ".join("%s (%s%s)" % (e["curso"].title(), _br(e["inicio"]), (" a " + _br(e["fim"])) if e.get("fim") else " em diante")
                           for e in res.get("estudos_pendentes") or [])
        par.append("Consta ainda matrícula em estudo sem remição no RSPE%s, a ser comprovada por certidão de frequência da unidade, para a "
                   "remição à razão de 1 dia de pena a cada 12 horas de frequência escolar, divididas em no mínimo 3 dias (LEP, art. 126, § 1º, I)."
                   % ((": " + cursos) if cursos else ""))
    if ats:
        ped = ("Requer-se a declaração da remição de %s%s, computados como pena cumprida para todos os fins (LEP, arts. 126, 128 e 129), ouvidos "
               "o Ministério Público e a defesa (LEP, art. 126, § 8º)%s." % (
                   _dias_txt(total), " e dos dias correspondentes ao estudo" if est_h >= 12 else "",
                   ", com a requisição da certidão de frequência escolar à unidade prisional" if est_h >= 12 else ""))
    else:
        ped = ("Requer-se a requisição da certidão de frequência escolar à unidade prisional e, com ela, a declaração da remição dos dias "
               "correspondentes ao estudo, computados como pena cumprida para todos os fins (LEP, arts. 126, § 1º, I, 128 e 129), ouvidos o "
               "Ministério Público e a defesa (LEP, art. 126, § 8º).")
    return "DA REMIÇÃO DE PENA\n" + " ".join(par) + "\n" + ped


def comparativo(r, f, hoje=None, conferidos=None, manuais=None):
    """Campos da aba Ficha disciplinar: colunas resumidas + uma linha por emprego (atestado x remição no RSPE)."""
    hoje = hoje or date.today()
    out = {"fd_tem": bool(f), "fd_cor": "cinza", "fd_sit": "Sem ficha", "fd_conduta": "", "fd_trab": "", "fd_remidos": "",
           "fd_atestar": "", "fd_estudo": "", "fd_faltas": "", "fd_linhas": [], "fd_dias": None}
    if not f:
        out["fd_linhas"] = [{"emp": "Ficha disciplinar não importada", "per": "", "dias": "", "at": "", "rspe": "", "sit": "Importe o PDF da Ficha Disciplinar (SIAPEN) pelo botão Importar PDFs", "cor": "cinza"}]
        return out
    linhas, res = quadro_trabalho(r, f, hoje, manuais)
    conferidos = set(conferidos or ())
    manuais = manuais or []
    blocos = res.get("blocos", [])
    marcaveis = 0
    for b in blocos:
        if b["tipo"] == "atestado":
            marcaveis += 1
            b["ok"] = b["chave"] in conferidos
        for i in b["itens"]:
            if i.get("chave"):
                marcaveis += 1
                i["ok"] = i["chave"] in conferidos
    rem_man = 0
    if manuais:
        its = []
        for m_ in manuais:
            d = m_.get("dados") or {}
            rem = _num(str(d.get("remidos") or "0").replace(",", ".")) if d.get("remidos") else 0
            if not (res.get("conc") and (d.get("tipo") or "Trabalho") == "Trabalho"):  # trabalho informado já entra na conciliação
                rem_man += rem
            info = " · ".join(x for x in [("nº %s" % d["numero"]) if d.get("numero") else "", ("%s trabalhados" % d["trabalhados"]) if d.get("trabalhados") else "",
                                          ("%s h" % d["horas"]) if d.get("horas") else "", ("%s remidos" % _fmtn(rem)) if rem else ""] if x)
            per = " a ".join(x for x in [d.get("inicio") or "", d.get("fim") or ""] if x) or "—"
            its.append({"emp": "%s%s" % (d.get("tipo") or "Outro", (" · " + d["descricao"]) if d.get("descricao") else ""), "un": d.get("unidade") or "—",
                        "per": per, "sit": info or "—", "cor": "", "id": m_["id"]})
        blocos.append({"tipo": "manual", "titulo": "Adicionados por você", "info": "fora da ficha (ex.: ENCCEJA, trabalho não registrado)", "itens": its})
    n_ok = sum(1 for b in blocos if b.get("ok")) + sum(1 for b in blocos for i in b["itens"] if i.get("ok"))
    C = res.get("conc")
    if C:
        # conciliação: tabela (A), pendências (B) e alertas de qualidade (C); a marca "conferido" de cada atestado é o
        # checklist manual, separado dos status automáticos
        for t in C["tabela"]:
            t["ok"] = t["chave"] in conferidos
        marcaveis += len(C["tabela"])
        n_ok += sum(1 for t in C["tabela"] if t["ok"])
        out["fd_conc"] = {"tabela": C["tabela"],
                          "pend": [{"data": _br(p_["data"].strftime("%d/%m/%Y")) if p_["data"] else "", "status": p_["status"], "texto": p_["texto"],
                                    "acao": p_["acao"], "cor": p_["cor"]} for p_ in C["pendencias"]],
                          "alertas": [{"tipo": a_["tipo"], "texto": a_["texto"]} for a_ in C["alertas"]]}
    res["remidos_manuais"] = rem_man
    # trabalho anterior a esta execução: fica só no resumo do cabeçalho
    linhas = [L for L in linhas if L["sit"] != "Anterior a esta execução"]
    trab = f.get("trabalho", [])
    em = [x for x in trab if not x.get("fim")]
    out["fd_trab"] = ("%s desde %s" % (_nome_emprego(em[-1]), em[-1]["inicio"])) if em else "sem trabalho em curso"
    ficha_total = res["remidos_execucao"] + res["remidos_estudo"] + rem_man
    out["fd_remidos"] = "%s / %s" % (_fmtn(ficha_total), _fmtn(res["homologados"]))
    # colunas objetivas: Sim / Não (o detalhe vai para o cabeçalho da linha expandida)
    out["fd_estudo"] = "Sim" if res["estudo_horas_pend"] >= 12 else "Não"
    out["fd_atestar"] = "Sim" if (res.get("sem_n") or res.get("em_curso_n")) else "Não"
    # situação: diz o que falta, sem rodeio (remição não homologada, trabalho sem atestado, estudo, baixa sem início)
    partes = []
    # vermelho = dias exatos a requerer (atestado sem remição, leitura peticionada, estudo com horas declaradas); amarelo = estimativa
    # (trabalho sem atestado, estudo sem horas declaradas) ou ponto a conferir - as mesmas origens da remição detalhada
    D_ = res.get("rem_det") or {}
    nh = res["pendentes"] or 0
    nl_sd = res.get("nl_sem_dias") or 0
    lei_d = (D_.get("leitura") or {}).get("dias") or 0
    est_decl = (res.get("estudo_horas_decl") or 0) >= 12
    est_pend = res["estudo_horas_pend"] >= 12
    if nh >= 1 or nl_sd:
        # "verificar peticionamento" só quando a ficha não registra o peticionamento de algum atestado pendente
        sem_pet = any(a["status"] == "NAO_LANCADO" and not a.get("peticionado") for a in ((res.get("conc") or {}).get("atestados") or []))
        partes.append("Atestado emitido não lançado no RSPE (%s) - %s" % (
            " + ".join(x for x in (("%s remidos" % _fmtn(nh)) if nh >= 1 else "", rs.pl(nl_sd, "atestado sem os dias na ficha", "atestados sem os dias na ficha") if nl_sd else "") if x),
            "conferir nos autos (se juntado, requerer a apreciação)" if sem_pet else "peticionado: requerer a apreciação"))
    elif res["diferenca"] >= 1:
        partes.append("Conferir remição: ficha %s%s × RSPE %s" % ("≈ " if res["remidos_estudo"] else "", _dias_txt(ficha_total), _dias_txt(res["homologados"])))
    if lei_d >= 1:
        partes.append("leitura peticionada sem remição no RSPE (%s)" % rs.pl(int(lei_d), "dia", "dias"))
    if res.get("sem_n"):
        partes.append("trabalho sem atestado (%d período%s)" % (res["sem_n"], "s" if res["sem_n"] > 1 else ""))
    n_lac = sum(1 for p_ in (C or {}).get("pendencias", []) if p_["status"] in ("LACUNA", "DIVERGENCIA"))
    if n_lac:
        partes.append("%s na conciliação (lacuna ou divergência de dias)" % rs.pl(n_lac, "ponto a conferir", "pontos a conferir"))
    if est_pend:
        partes.append("estudo a requerer (%s%s)" % ("" if est_decl else "≈ ", rs.pl(res["estudo_dias_pend"], "dia", "dias")))
    if res["baixas"] and not partes:
        partes.append("trabalho sem início registrado")
    # último atestado há mais de 6 meses, com trabalho em curso
    ult = None
    for a in f.get("atestados", []):
        d = _d(a.get("periodo_fim") or "") or _d(a.get("data") or "")
        if d and (ult is None or d > ult):
            ult = d
    if C:
        ult = max([x["fim"] for a in C["atestados"] if a["origem"] != "rspe" for x in a["segs"] if x["fim"]] or [None]) or ult
    velho = bool(em and ult and (hoje - ult).days > 183)
    if velho:
        partes.append("último atestado há mais de 6 meses (período até %s)" % ult.strftime("%d/%m/%Y"))
    # situação objetiva na coluna; o texto completo fica no cabeçalho da linha expandida
    rot = []
    if nh >= 1 or nl_sd:
        rot.append("Atestado não lançado")
    if lei_d >= 1 or est_decl:
        rot.append("Remição a requerer")
    elif est_pend:
        rot.append("Estudo sem remição (estimativa)")
    if not (nh >= 1 or nl_sd) and res["diferenca"] >= 1:
        rot.append("Conferir remição")
    if n_lac and "Conferir remição" not in rot:
        rot.append("Conferir remição")
    if res.get("sem_n") or (res["baixas"] and not rot):
        rot.append("Ausência de atestado")
    if velho:
        rot.append("Último atestado há 6 meses")
    if partes:
        cor = "vermelho" if (nh >= 1 or nl_sd or lei_d >= 1 or est_decl) else "amarelo"
        det = "; ".join(partes)
        det = det[0].upper() + det[1:]
        sit = " · ".join(rot) or det
    else:
        cor, sit, det = "verde", "Em ordem", ""
    out["fd_sit_det"] = det
    faltas = f.get("faltas", [])
    out["fd_faltas"] = ("%d (%s)" % (len(faltas), ", ".join(x["situacao"] for x in faltas))) if faltas else "nenhuma"
    out["fd_remicoes"] = ("Remições no RSPE: " + " · ".join("%s em %s" % (_dias_txt(i["dias"]), i["data"]) for i in res["remicoes"]) +
                          ". O RSPE não diz a origem de cada uma (trabalho, estudo, ENCCEJA/ENEM, leitura).") if res["remicoes"] else "Nenhuma remição no RSPE."
    out["fd_resumo_exec"] = "atestados: %s · estudo: ≈ %s · RSPE: %s%s%s" % (
        _dias_txt(res["remidos_execucao"]), _dias_txt(res["remidos_estudo"]), _dias_txt(res["homologados"]), (" · adicionados por você: %s" % _dias_txt(rem_man)) if rem_man else "",
        (" · anteriores a esta execução: %s" % _dias_txt(res["remidos_anteriores"])) if res["remidos_anteriores"] else "")
    out["fd_fund"] = fundamentacao_remicao(res)
    out.update(fd_cor=cor, fd_sit=sit, fd_conduta=f.get("conduta") or "", fd_linhas=linhas,
               fd_blocos=blocos, fd_conf_n=n_ok, fd_conf_tot=marcaveis, fd_sem_n=res.get("sem_n", 0),
               fd_sem_pend=res.get("sem_atestado_a_requerer", 0), fd_rem_det=res.get("rem_det"))
    return out


# --------------------------------------------------------------------------- #
# indulto: incisos que dependem da ficha (saídas temporárias, trabalho externo, estudo, curso concluído)
# --------------------------------------------------------------------------- #

def _dias_no_intervalo(periodos, a, b):
    """Dias (sem contar duas vezes) dos períodos [(ini, fim)] dentro de [a, b]."""
    dias = set()
    for i, f in periodos:
        if not i:
            continue
        i2, f2 = max(i, a), min(f or b, b)
        d = i2
        while d <= f2:
            dias.add(d)
            d += timedelta(days=1)
    return len(dias)


RE_SAIDA_LIVRE = _ReFicha(re.compile(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(ALVAR|SOLTURA|LIBERDADE|FUGA|EVAS|DETERMINA[ÇC][ÃA]O JUDICIAL|LIVRAMENTO|"
                                     r"T[ÉE]RMINO|EXTIN|CUMPRIMENTO DE PENA|DOMICILIAR)|ALVAR[ÁA] DE SOLTURA|\bFUGA\b|EVADIU|EVAS[ÃA]O|FORAGID|N[ÃA]O RETORNOU", re.I))
RE_ENTRADA_RUA = re.compile(r"(ENTRADA NA UNIDADE PENAL|DEU ENTRADA).*(PROCEDENTE:\s*(DP\b|DEPAC|DELEGACIA|CEPOL|CPAC)|PROVINDO DA DELEGACIA|"
                            r"AUDI[ÊE]NCIA DE CUST[ÓO]DIA)|ENTRADA NA UNIDADE PENAL:\s*CENTRAL PROVIS[ÓO]RIA DE AUDI[ÊE]NCIA DE CUST[ÓO]DIA", re.I)


def custodia_na_ficha(f, ini, datas):
    """Inciso IV (custódia ininterrupta): confronta cada nova prisão que o RSPE registra dentro do período contínuo com a
    movimentação da ficha disciplinar. (True, nota): a ficha mostra a pessoa custodiada antes e depois, sem soltura, fuga
    ou evasão - a prisão ocorreu durante a custódia e não interrompe; (False, nota): a ficha registra saída em liberdade
    (alvará, fuga, evasão) ou entrada vinda da delegacia/audiência de custódia; (None, nota): a ficha não cobre a data."""
    ev = sorted(((_dp(e["data"]), e["texto"]) for e in f.get("eventos", []) if _dp(e.get("data") or "")), key=lambda x: x[0])
    if not ev or not datas:
        return None, ""
    notas, res = [], True
    for d in datas:
        livres = [(x, t) for x, t in ev if ini < x <= d and RE_SAIDA_LIVRE.search(t)]
        rua = [(x, t) for x, t in ev if max(d - timedelta(days=10), ini + timedelta(days=5)) < x <= d + timedelta(days=20) and RE_ENTRADA_RUA.search(t)]
        if livres or rua:
            partes = []
            if livres:
                x, t = livres[-1]
                mm = re.search(r"MOTIVO:\s*([^,]+)", t, re.I)
                partes.append("saída em %s (%s)" % (rs.fmt(x), mm.group(1).strip().lower() if mm else _br(t)[:80].rstrip(" ,.")))
            if rua:
                x, t = rua[0]
                mm = re.search(r"PROCEDENTE:\s*([^,]+)", t, re.I)
                partes.append("entrada em %s vinda de %s" % (rs.fmt(x), mm.group(1).strip() if mm else "fora do sistema prisional"))
            notas.append("ficha: %s - houve interrupção antes da prisão de %s" % ("; ".join(partes), rs.fmt(d)))
            res = False
            continue
        antes = [x for x, _ in ev if d - timedelta(days=365) <= x < d]
        depois = [x for x, _ in ev if d < x <= d + timedelta(days=365)]
        if not antes or not depois:
            notas.append("ficha sem movimentação ao redor de %s (registros desde %s) - conferir nos autos" % (rs.fmt(d), rs.fmt(ev[0][0])))
            if res is True:
                res = None
            continue
        notas.append("ficha: custodiado antes e depois de %s (registros desde %s), sem soltura, fuga ou evasão desde %s - a prisão ocorreu "
                     "durante a custódia e não interrompe o período" % (rs.fmt(d), rs.fmt(ev[0][0]), rs.fmt(max(ini, ev[0][0]))))
    return res, "; ".join(notas)


def complementar_decretos(r, f, hoje=None):
    """Decretos 12.338/2024 e 12.790/2025, art. 9º, XI, XII e XIII: o RSPE não traz saídas temporárias, trabalho externo,
    estudo nem curso concluído; a ficha traz. Resolve pela ficha os incisos que o cálculo deixou "a verificar"
    (a fração e o teto de pena já foram conferidos). Altera r no lugar."""
    if not f:
        return
    hoje = hoje or date.today()
    ev = f.get("eventos", [])
    saidas = sorted(d for d in (_dp(e["data"]) for e in ev if re.search(r"SA[ÍI]DA CONFIRMADA DO BENEF[ÍI]CIO DE:\s*SA[ÍI]DA TEMPOR", e["texto"].upper())) if d)
    externos = [(_dp(t["inicio"]), _dp(t.get("fim") or "")) for t in f.get("trabalho", []) if t.get("externo")]
    estudos = [(_dp(e["inicio"]), _dp(e.get("fim") or "") or hoje, e) for e in f.get("estudos", []) if _dp(e.get("inicio") or "")]
    ini_exec = min((rs.to_date(e.get("data") or "") for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), default=None)
    for ano in ("2024", "2025"):
        k, kc = "indulto_%s" % ano, "comutacao_%s" % ano
        det = r.get(k + "_detalhe") or ""
        if not re.search(r"^\? (IV|XI|XII|XIII):", det, re.M):
            continue
        ref = rs.DECRETOS.get(ano)
        if not ref:
            continue
        reinc = bool(re.search(r"Situação em [\d/]+:[^\n]*\breincidente", det))
        res = {}
        # XI: 5 saídas temporárias usufruídas até a data, ou 12 meses de trabalho externo nos 3 anos anteriores
        ns = len([d for d in saidas if d <= ref])
        dext = _dias_no_intervalo(externos, ref - timedelta(days=3 * 365), ref)
        if ns >= 5:
            res["XI"] = (True, "ficha: %d saídas temporárias até %s (última em %s)" % (ns, rs.fmt(ref), rs.fmt(max(d for d in saidas if d <= ref))))
        elif dext >= 360:
            res["XI"] = (True, "ficha: %s de trabalho externo nos 3 anos anteriores" % rs.pl(dext, "dia", "dias"))
        else:
            res["XI"] = (False, "ficha: %s até %s e %s de trabalho externo nos 3 anos anteriores" % (rs.pl(ns, "saída temporária", "saídas temporárias"), rs.fmt(ref), rs.pl(dext, "dia", "dias")))
        # XII: estudo (fundamental, médio, superior, profissionalizante) por 12 meses nos 3 anos anteriores
        # (reincidente: 18 meses nos 5 anos anteriores - Decretos 2024 e 2025, art. 9º, XII)
        meses, anos_j = (18, 5) if reinc else (12, 3)
        dest = _dias_no_intervalo([(a, b) for a, b, _ in estudos], ref - timedelta(days=anos_j * 365), ref)
        res["XII"] = ((dest >= meses * 30), "ficha: %s de matrícula em estudo nos %s anteriores (exige %s)" % (rs.pl(dest, "dia", "dias"), rs.pl(anos_j, "ano", "anos"), rs.pl(meses, "mês", "meses")))
        # XIII: curso concluído durante a execução (ENCCEJA/ENEM certificado, ou curso concluído na ficha)
        # XIII: conclusão durante a execução e nos 3 anos anteriores à data do decreto
        j13 = ref - timedelta(days=3 * 365)
        exs13 = [x for x in f.get("exames", []) if j13 <= (_dp(x["data"]) or date.min) <= ref and (not ini_exec or (_dp(x["data"]) or date.min) >= ini_exec)]
        def _cert(x):
            if "certificado" in x:
                return x["certificado"]
            # ficha gravada antes desta versão (sem a marca): pelo texto do registro do mesmo dia
            us = [e["texto"].upper() for e in ev if e.get("data") == x["data"] and x["exame"].split()[0] in (e.get("texto") or "").upper()]
            return x["exame"].startswith("ENCCEJA") and any("CERTIFICAD" in u and not re.search(r"PARCIAL|NA AREA|NA ÁREA|POR AREA|POR ÁREA", u) for u in us)
        conc = [x for x in exs13 if _cert(x)]
        exs_ver = [x for x in exs13 if x not in conc]  # ENEM ou ENCCEJA sem certificado de conclusão: a verificar
        conc += [{"exame": e["curso"].title(), "data": e.get("fim")} for a, b, e in estudos
                 if "CONCLU" in (e.get("motivo_fim") or "").upper() and j13 <= b <= ref and (not ini_exec or a >= ini_exec)]
        livres = [e for a, b, e in estudos if e.get("horas") and j13 <= b <= ref and (not ini_exec or a >= ini_exec) and "CONCLU" not in (e.get("motivo_fim") or "").upper()]
        if conc:
            res["XIII"] = (True, "ficha: %s" % "; ".join("%s (certificado registrado em %s)" % (x["exame"], _br(x["data"] or "")) for x in conc))
        elif exs_ver:
            res["XIII"] = (None, "ficha: %s - conferir se houve conclusão de curso certificada (o ENEM não certifica a conclusão do ensino médio "
                                 "desde 2017; petição, declaração parcial ou aprovação por área não é certificado de conclusão)" % "; ".join(
                                     "%s em %s" % (x["exame"], _br(x["data"] or "")) for x in exs_ver))
        elif livres:
            res["XIII"] = (None, "ficha: curso %s (%d h, %s a %s) - conferir se é profissionalizante com certificado" % (
                livres[0]["curso"].title(), livres[0]["horas"], _br(livres[0]["inicio"]), _br(livres[0]["fim"])))
        else:
            res["XIII"] = (False, "ficha: nenhum curso concluído nem certificado ENCCEJA/ENEM entre %s e %s" % (rs.fmt(j13), rs.fmt(ref)))
        # IV: nova prisão dentro do período contínuo - a movimentação da ficha diz se houve interrupção
        m4 = re.search(r"^\? IV: .*?desde (\d{2}/\d{2}/\d{4}).*verificar se houve interrupção no período: (.*)$", det, re.M)
        if m4:
            ok4, nota4 = custodia_na_ficha(f, rs.to_date(m4.group(1)), sorted({rs.to_date(x) for x in re.findall(r"\d{2}/\d{2}/\d{4}", m4.group(2))} - {None}))
            if nota4:
                res["IV"] = (ok4, nota4)
        # ressalva da análise (violência doméstica provável, livramento incerto, crime militar): a ficha não a resolve
        ressalva = r.get(k + "_ressalva") or ""
        # reescreve as linhas "? XI/XII/XIII" do detalhe e da explicação
        novas, poss, verif = [], [], []
        for l in det.split("\n"):
            m = re.match(r"^\? (IV|XI|XII|XIII): (.*)$", l)
            if m and m.group(1) in res:
                ok, nota = res[m.group(1)]
                txt = re.sub(r"\s*-\s*verificar .*$", "", m.group(2))
                l = "%s %s: %s - %s%s" % ({True: "✔", False: "✘", None: "?"}[ok], m.group(1), txt, nota, (" - " + ressalva) if (ok and ressalva) else "")
            novas.append(l)
        det = "\n".join(novas)
        r[k + "_detalhe"] = det
        exp = r.get(k + "_explica") or ""
        if exp:
            ex2 = []
            for l in exp.split("\n"):
                m = re.match(r"^\? Inciso (IV|XI|XII|XIII): ", l)
                if m and m.group(1) in res:
                    ok, nota = res[m.group(1)]
                    l = re.sub(r"\s*Depende de dado que o RSPE não traz\.?", "", l)
                    l = re.sub(r"\s*-\s*verificar [^.]*(\.|\([^)]*\)\.)", ".", l, count=1)
                    l = "%s%s · %s." % ({True: "✔", False: "✘", None: "?"}[ok], l[1:].rstrip(". "), nota[0].upper() + nota[1:]) if nota else l
                ex2.append(l)
            exp = "\n".join(ex2)
        # nova conclusão pelo conjunto das linhas
        poss = [m.group(1) for m in re.finditer(r"^✔ ([IVX]+(?: e [IVX]+)?):", det, re.M)]
        verif = [m.group(1) for m in re.finditer(r"^\? ([IVX]+):", det, re.M) if m.group(1) not in ("XVI",)]
        antes = r.get(k) or ""
        # NÃO CABE (art. 6º, falta grave nos 12 meses): a ficha não reabre - a falta afasta o indulto qualquer que seja o inciso
        if antes.startswith(("CONCEDIDO", "INDEFERIDO", "não se aplica", "VEDAD", "excluído", "NÃO CABE")) or r.get(k + "_status") in ("vedado",):
            r[k + "_explica"] = exp
            continue
        # avisos da análise (falta do art. 6º, livramento incerto etc.) seguem na célula depois de " | "
        aviso = (" | " + antes.split(" | ", 1)[1]) if " | " in antes else ""
        rot = ""
        mrot = re.match(r"^(?:POSSÍVEL|A VERIFICAR) \(([^)]*)\)", antes)
        if mrot:
            rot = " (%s)" % mrot.group(1)
        elif "Art. 7º, p. ú.: 2/3 da pena dos impeditivos cumpridos" in det:
            rot = " (crimes não impeditivos, art. 7º, p. ú.)"
        if mrot and antes.startswith("A VERIFICAR") and not ressalva:
            # "A VERIFICAR (tese: hediondez superveniente)" ou "(art. 2º, II)": motivo que a ficha não resolve - segue a verificar
            ressalva = mrot.group(1)
        if poss and ressalva:
            # a ficha confirma o requisito, mas a ressalva continua: segue "a verificar"
            r[k] = "A VERIFICAR%s: art. 9º, %s%s" % (rot, ", ".join(dict.fromkeys(poss + verif)), aviso)
            r[k + "_status"] = "verificar"
            concl = "a verificar (%s) - %s." % (", ".join(dict.fromkeys(poss + verif)), ressalva)
        elif poss:
            r[k] = "POSSÍVEL%s: art. 9º, %s%s" % (rot, ", ".join(poss), aviso)
            r[k + "_status"] = "possivel"
            if (r.get(kc) or "").startswith("POSSÍVEL"):
                r[kc] = "prejudicada: indulto cabível (art. 13, § 5º)"
            concl = "possível pelo art. 9º, %s (conferido na ficha disciplinar)." % ", ".join(poss)
        elif verif:
            r[k] = "A VERIFICAR%s: art. 9º, %s%s" % (rot, ", ".join(verif), aviso)
            r[k + "_status"] = "verificar"
            concl = "a verificar (%s)." % ", ".join(verif)
        else:
            r[k] = "não atinge: incisos conferidos na ficha disciplinar não atendidos" + aviso
            r[k + "_status"] = "nao"
            concl = "não atinge nenhum inciso nesta data (%s conferidos na ficha disciplinar)." % ", ".join(k2 for k2 in ("IV", "XI", "XII", "XIII") if k2 in res)
        r[k + "_explica"] = re.sub(r"^Conclusão: .*$", "Conclusão: " + concl, exp, flags=re.M) if exp else exp
