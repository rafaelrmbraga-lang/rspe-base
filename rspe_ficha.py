# -*- coding: utf-8 -*-
"""
Leitura da Ficha Disciplinar do SIAPEN (AGEPEN/MS) e confronto com o RSPE.

Extrai: identificação, conduta, períodos de trabalho (setor/empresa), atestados de trabalho
(dias trabalhados e remidos), faltas disciplinares (registro, PADIC, resultado), regressão/
restabelecimento e recusa de trabalho. Compara os dias remidos atestados com o saldo do RSPE
(LEP, arts. 126 a 128) e a existência de falta grave (LEP, art. 50; CP, art. 83, III, b).
"""
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
    # tolerante a acentos, maiúsculas/minúsculas, espaços e quebras de linha no título e ao cabeçalho do sistema (SIAPEN ou AGEPEN)
    t = rs._norm_marca(texto)
    return bool(re.search(r"FICHA ?DISCIPLINAR", t)) and ("SIAPEN" in t or "AGEPEN" in t or "PENITENCI" in t)


def _limpar(t):
    # remove cabeçalhos/rodapés repetidos do SIAPEN
    out = []
    for l in t.splitlines():
        u = l.strip()
        if not u:
            continue
        # (o rodapé "RUA:/CEP:/FONE:" sai pela fonte, em _pagina_historico: aqui a linha de um lançamento que começa com "RUA:" fica)
        if re.search(r"Confidencial ::|Responsável:|Projeto SIAPEN|^\d{2}:\d{2}:\d{2}$|^RRMB|^\d{2}:\d{2}: ", u):
            continue
        # login de quem imprimiu, no topo de cada página ("RSS (8002969) em: 02/10/2026"): sozinho ou colado no fim da linha
        u = re.sub(r"\s*\b[A-Z0-9]{2,12}\s*\(\d{5,}\)\s*em:\s*\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?\s*$", "", u)
        if not u:
            continue
        out.append(u)
    return "\n".join(out)


MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "MARCO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8,
         "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}


def _estudos(eventos, cancel_sem=None):
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
        # saída da unidade (transferência, soltura, evasão, progressão): a matrícula na escola da unidade termina aí
        uf = _sem_fuga_falsa(e["texto"])
        msai = re.match(r"\W*SAIDA DA UNIDADE PENAL:.*?MOTIVO:\s*([^,]*)", uf)
        if e.get("data") and [p for p in abertos if not p.get("livre")] and (
                (msai and not re.search(r"TEMPORARIA|AUDIENCIA|MEDIC|HOSPITAL|SAUDE|ESCOLTA|TRABALHO|ATENDIMENTO|JURI|DUPLICIDADE", msai.group(1)))
                or (not msai and re.search(r"\bTRANSFERID[OA] PARA\b|\bEVADI\w*|\bEVASAO\b|\bFUGA\b|EMPREENDEU FUGA|POSTO EM LIBERDADE|COLOCADO EM LIBERDADE", uf))):
            for p in [p for p in abertos if not p.get("livre")]:
                fechar(p, e["data"], "saída da unidade" + ((" (%s)" % msai.group(1).strip(" .").lower()) if msai and msai.group(1).strip(" .") else ""))
        if not re.search(r"EDUCA|\bCURSO\b|ESCOLA|ESTUD|ALUNOS|HORAS?.AULA", us):
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
            # (7.14.5) "atestado de horas aulas, remir (180) cento e oitenta horas aulas": o número (com o extenso repetido) antes de "horas aulas"
            mh = mh or re.search(r"(?<![\d,.])(\d+)\s+(?:%s\s+)*HORAS?.AULAS?\b()" % rrm._NUM_EXT, ua)
            if mh:
                ini = rrm._dt(mp.group(1)).strftime("%d.%m.%Y") if mp and rrm._dt(mp.group(1)) else e["data"]
                fim = rrm._dt(mp.group(2)).strftime("%d.%m.%Y") if mp and rrm._dt(mp.group(2)) else ""
                nat = re.search(r"\bATP\s*(?:N\S*\s*)?(\d+/\d+)|ATESTADO\D{0,30}?N?\W{0,3}(\d+/\d+)", ua)
                num = (nat.group(1) or nat.group(2)) if nat else ""
                p = {"curso": "Atestado de estudo" + (" nº " + num if num else ""), "turma": "", "turno": "", "inicio": ini, "fim": fim or ini,
                     "motivo_fim": "atestado de estudo" if fim else "carga horária declarada", "horas": int(mh.group(1) or mh.group(2)), "livre": True}
                # (7.14.3) os dias de remição declarados no atestado ("com 06 dias a serem remidos"): o atestado é documento da comparação
                md_ = re.search(r"(?<![\d,.])(\d{1,3}(?:[,.]\d{1,2})?)\s*DIAS?\s*(?:A SEREM\s*)?REMID", ua)
                if md_ and float(md_.group(1).replace(",", ".")):
                    p.update(dias_remidos=float(md_.group(1).replace(",", ".")), data=e["data"], texto=e["texto"])
                elif re.search(r"\bREMIR\b", ua) and mh.group(2) == "":
                    # (7.14.5) "atestado de horas aulas, remir (180) horas aulas": as horas a remir são o documento (12 h = 1 dia, LEP,
                    # art. 126, § 1º, I) - entra na comparação como o atestado de estudo com dias declarados
                    p.update(dias_remidos=round(p["horas"] / 12.0, 2), data=e["data"], texto=e["texto"])
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
        if re.search(r"DESISTENCIA D[AO]S? (?:ESCOLA|ESTUDOS?)|DESISTIU D[AO]S? (?:ESCOLA|ESTUDOS?)", us):
            # (7.14.1) desistência registrada só na mudança de cela ("Motivo: DESISTÊNCIA DA ESCOLA"): fim do estudo em curso
            for p in [p for p in abertos if not p.get("livre")]:
                fechar(p, e["data"], "desistência da escola")
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
            if cancel_sem is not None and not abertos and "CANCELAMENTO" in u and e.get("data") and not any(
                    (_dp(p["inicio"]) or date.max) <= (_dp(e["data"]) or date.min) for p in out):
                # matrícula cancelada sem a matrícula registrada na ficha: houve estudo cujo período a ficha não mostra
                cancel_sem.append({"data": e["data"], "texto": e["texto"]})
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
            # o mesmo curso citado de novo (ex.: início remarcado) substitui o registro anterior: mesmo nome completo e períodos que se
            # sobrepõem ("INFORMATICA BASICA" e "INFORMATICA AVANCADA", ou o mesmo curso em outro ano, são cursos diferentes);
            # curso sem nome não se confunde com outro
            _ini_n, _fim_n = _dp(ini), _dp(fim or ini)
            ant = [p for p in out if p.get("livre") and re.sub(r"\W", "", p["curso"]) == re.sub(r"\W", "", nome) and nome != "curso"
                   and _ini_n and _dp(p["inicio"]) and _dp(p["inicio"]) <= (_fim_n or _ini_n) + timedelta(days=60)
                   and (_dp(p["fim"]) or _dp(p["inicio"])) >= _ini_n - timedelta(days=60)]
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
    for m in re.finditer(r"\b(?:DA|DO|NA)\s+(?:LEP\b|LEI\s*(?:N[ºO°.]?\W{0,3}\s*)?7\.?210|LEI DE EXECU)", u):
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
                 r"CIENCIA DA DECISAO/CONCLUSAO|PRATICOU FALTA|IMPUTADO (?:N?O )?COMETIMENTO|COMETEU FALTA|CIENCIA D[AO] (?:DECISAO|PADIC|PROCESSO|SANCAO|CONCLUSAO)|CIENTIFICADO DA CONCLUSAO|"
                 r"TOMOU CONHECIMENTO DA DECISAO|O QUAL (?:CONCLUIU|SUGERIU)|ACATOU A PROPOSICAO DE SANCAO")
# parecer, resumo da ficha ou decisão judicial (regressão, reconhecimento da falta): não é falta nova - casa com a falta do fato
_RE_NARRATIVA = r"PARECER|EM SUA FICHA CONSTA|CONSTA (?:EM SUA|NA) FICHA|^REGRESSAO DE REGIME|RECONHECO A PRATICA"
# data do fato no registro do resultado
_RE_FATO_RES = (r"(?:NA DATA DE|DATA DOS FATOS\W*(?:EM\s*)?|FATO OCORRIDO (?:NO DIA|EM)|DO FATO OCORRIDO NO DIA|A CONTAR DA DATA DE|A CONTAR DE|"
                r"(?:REFERENTE AO )?OCORRIDO EM|FALTA DISCIPLINAR (?:DE NATUREZA )?(?:GRAVE|MEDIA|LEVE)\s*,?\s*EM|"
                r"DATA D[OA] (?:COMETIMENTO DA )?(?:FATO|FALTA|OCORRIDO)(?: COMETIDA)?\W*(?:OU SEJA\W*)?)\s*(\d{2}/\d{2}/\d{2}(?:\d{2})?)\b")


def _texto_falta(t):
    """Texto do lançamento para a leitura das faltas: sem acento, maiúsculo, sem aspas ("FALTA DISCIPLINAR "GRAVE"", "´MÁ´") e com os
    erros de digitação das fichas antigas corrigidos ("NATUREA GRAVE", "nateure GRAVE", "FATA DE NATUREZA", "ocorriido", "diisciplinar")."""
    u = rs._sem_acento(t or "").upper()
    u = re.sub(r"[\"'´`“”]", "", u)
    u = re.sub(r"\bNATU?R?E[UR]?[AE]?\b(?= (?:GRAVE|MEDIA|LEVE))|\bNATUREA\b|\bNATEURE\b", "NATUREZA", u)
    u = re.sub(r"\bFATA DE NATUREZA", "FALTA DE NATUREZA", u)
    u = re.sub(r"OCORRIIDO", "OCORRIDO", u)
    u = re.sub(r"DIISCIPLINAR", "DISCIPLINAR", u)
    u = re.sub(r"\bDECIDSAO\b", "DECISAO", u)
    return re.sub(r"\s+", " ", u)


def num_padic(u):
    """Número do PADIC/PAD/processo disciplinar citado no lançamento, só os algarismos ("PADIC / CPAIG Nº 31/620.936/2019",
    "PAD. Nº 31/620.936/2019", "PADIC n°31/090.198/2022", "Processo Disciplinar nº 31/618.006/12"): casa os lançamentos do mesmo processo."""
    u = rs._sem_acento(u or "").upper()
    mp = re.search(r"(?:\bPADIC\b|\bPAD\b\.?|CD SIMPLIFICADA|PROCESSO DISCIPLINAR|\bNUP\b)\s*(?:/\s*[\w-]+\s*)?(?:N\S{0,2})?\s*(3\d[\d./-]{5,}\d)", u)
    return re.sub(r"\D", "", mp.group(1)) if mp else ""
# não é falta: retorno da conduta depois de cumprida a sanção; aviso do setor de educação
_RE_NAO_FALTA = r"RETORNA (?:AO COMPORTAMENTO|O PARECER|SUA CONDUTA)|^EDUCACAO:"


def _e_isolamento(t):
    """Lançamento de isolamento (lista exibida): na mudança de cela, só quando o DESTINO é cela disciplinar, correcional ou de
    isolamento (a cela disciplinar só na origem é a saída do isolamento); nos demais, a menção a isolamento ou cela disciplinar."""
    u = rs._sem_acento(t or "").upper()
    if u.startswith("MUDANCA DE CELA"):
        md = re.search(r"DESTINO:\s*(.*?)(?:,\s*CONFORME|$)", u)
        # (a cela de seguro pedida pelo preso não é isolamento)
        return bool(md and re.search(r"DISCIPLIN|CORRECIONAL|ISOLAMENTO", md.group(1)) and not re.search(r"MOTIVO:[^,]*SEGURO", u)) \
            or _cela_por_sancao(t)
    # o fim do isolamento não é isolamento: "Retornou ao convívio após cumprir isolamento", "TÉRMINO DO ISOLAMENTO", "SAI DA CELA
    # DISCIPLINAR (e passa à condição de sancionado)"
    if re.search(_RE_FIM_ISOLAMENTO, u):
        return False
    return bool(re.search(r"ISOLADO|ISOLAMENTO|CELA DISCIPLINAR", u))


# (no início do lançamento: "devendo retornar ao convívio" ou "quer retornar ao convívio" num registro de isolamento não é o fim dele)
_RE_FIM_ISOLAMENTO = (r"^\W*(?:EM \d{2}/\d{2}/\d{2,4}\W*)?(?:NESTA DATA\W*)?(?:O (?:MESMO|INTERNO|PRESO|REEDUCANDO)\s+)?"
                      r"(?:RETORNOU AO CONVIVIO|TERMINO D[OA] ISOLAMENTO|FIM D[OA] ISOLAMENTO|SAI(?:U)? DA CELA DISCIPLINAR)")


def _cela_por_sancao(t):
    """Mudança de cela por sanção ("Motivo: SANCIONADO", "CELA SANCIONADA POR FALTA GRAVE"; destino correcional ou não): indício
    de isolamento, só para a lista exibida (conferir a sanção). Não cria falta nem entra em contagem (a falta vem do PADIC/CD)."""
    u = rs._sem_acento(t or "").upper()
    mm = re.search(r"MOTIVO:\s*([^,]*)", u)
    return bool(u.startswith("MUDANCA DE CELA") and mm and re.search(r"\bSANCIONAD", mm.group(1))
                and not re.search(r"FIM D[OA]|CUMPRID|TERMINO|RETORNO|SEGURO|\bSAI(?:U|R)? DA CELA", mm.group(1)))


def cpf_cabecalho(cab):
    """CPF do cabeçalho da ficha, com pontos ("060.395.731-55") ou com espaços no lugar deles ("060 395 731-55", "701 076 621 59"):
    guardado no formato com pontos."""
    mcpf = re.search(r"CPF:[ \t]*(\d{3})[. ]?(\d{3})[. ]?(\d{3}) ?[-. ]? ?(\d{2})(?!\d)", cab or "")
    return ("%s.%s.%s-%s" % mcpf.groups()) if mcpf else (re.search(r"CPF:\s*([\d.\-]+\d)", cab or "") or [None, ""])[1]


def filiacao_cabecalho(cab):
    """Filiação do cabeçalho; o "Nº Pront Saúde" pode vir colado ao nome ("...ALBUQUERQUENº Pront Saúde: PDIB - 52.281")."""
    mfi = re.search(r"Filia[çc][ãa]o:\s*(.+?)(?:\s*N[ºo°]\s*Pront|\n|$)", cab or "")
    return mfi.group(1).strip() if mfi else ""


def _pagina_historico(p, k):
    """Texto da página só com o que é visível no histórico do SIAPEN (Times 8 pt). Fica de fora: o "histórico antigo" em Times
    10 pt que vem na camada de texto, cortado na impressão (só a 1ª linha aparece), e que embaralhava as linhas do lançamento
    (devolvido à parte, sem virar lançamento); e o rodapé (endereço e telefone em 7 pt, "Nome: ... Projeto SIAPEN" e a 2ª linha
    de um nome comprido). Na 1ª página, o cabeçalho (acima de "HISTÓRICO") fica inteiro. Devolve (texto, linhas ocultas)."""
    chars = getattr(p, "chars", None)
    if not chars:
        # página sem a posição dos caracteres (PDF sem camada de caracteres ou leitor simplificado): o texto corrido
        return p.extract_text() or "", []
    topo = 0
    if k == 0:
        w = next((w for w in p.extract_words() if re.match(r"HIST[ÓO]RICO", w["text"], re.I)), None)
        if w is None:
            return p.extract_text() or "", []
        topo = w["bottom"]
    pe = [c for c in p.chars if c["top"] >= topo and round(c["size"]) == 7]
    rodape = min((c["top"] for c in pe if c["top"] > p.height * 0.5), default=None)

    def oculto(c):
        return c["top"] >= topo and round(c["size"]) == 10 and "BOLD" not in (c.get("fontname") or "").upper()

    def fora(o):
        if o.get("object_type") != "char" or o["top"] < topo:
            return False
        return oculto(o) or round(o["size"]) == 7 or (rodape is not None and o["top"] >= rodape - 1)
    vis = p.filter(lambda o: not fora(o)).extract_text() or ""
    occ = []
    if any(oculto(c) for c in p.chars):
        occ = [x for x in rs.sem_linhas_navegador(p.filter(lambda o: o.get("object_type") != "char" or oculto(o)).extract_text() or "")[0]
               .splitlines() if x.strip()]
    return vis, occ


def data_prisao_cabecalho(cab):
    """Data da prisão do cabeçalho. Às vezes outra célula vem intercalada na camada de texto ("Data Prisão: AVÓ-D0O6L/1O2R/2E0S1)5"
    = 06/12/2015) ou uma palavra se interpõe ("Data Prisão: COM 29/04/2009"): vale a primeira data dd/mm/aaaa nos algarismos do
    trecho até o próximo rótulo."""
    m = re.search(r"Data Prisão:[ \t]*(\d{2}/\d{2}/\d{4})", cab or "")
    if m:
        return m.group(1)
    m = re.search(r"Data Prisão:[ \t]*([^\n]{0,40}?)(?:\s+Proced[êe]ncia:|\s+Condena[çc][ãa]o:|\n|$)", cab or "")
    if m:
        mm = re.match(r"\D{0,12}?(\d{2}/\d{2}/\d{4})", m.group(1)) or re.match(r"(\d{2}/\d{2}/\d{4})", re.sub(r"[^\d/]", "", m.group(1)))
        if mm and _dp(mm.group(1).replace("/", ".")):
            return mm.group(1)
    return ""


def _data_prisao_chars(p):
    """Data da prisão pelos caracteres da 1ª página: os da linha do valor (mesmo topo) entre "Data Prisão:" e "Procedência:", sem a
    célula vizinha que a camada de texto intercala ("ROCHA0,73/7045 /I2P0A2C4ARAI" = "07/05/2024" + "ROCHA, 374 IPACARAI")."""
    import collections
    if not getattr(p, "chars", None):
        return ""
    neg = [c for c in p.chars if "BOLD" in (c.get("fontname") or "").upper()]
    txt = "".join(c["text"] for c in neg)
    i, j = txt.find("Data Prisão:"), txt.find("Procedência:")
    if i < 0 or j < 0:
        return ""
    lab, nxt = neg[i + len("Data Prisão:") - 1], neg[j]
    cs = [c for c in p.chars if abs(c["top"] - lab["top"]) < 9 and lab["x1"] <= c["x0"] < nxt["x0"] and "BOLD" not in (c.get("fontname") or "").upper()]
    g = collections.defaultdict(str)
    for c in sorted(cs, key=lambda c: c["x0"]):
        g[round(c["top"], 1)] += c["text"]
    for k in sorted(g, key=lambda k: abs(k - lab["top"])):
        m = re.match(r"\s*(\d{2}/\d{2}/\d{4})", g[k])
        if m and _dp(m.group(1).replace("/", ".")):
            return m.group(1)
    return ""


def extrair(caminho):
    """Leitura da ficha. Recusa só o que não é ficha (ValueError com o motivo); o que faltar ou falhar numa parte (cabeçalho,
    histórico, análise) vira "_leitura_parcial", sem derrubar a leitura."""
    try:
        pdf = pdfplumber.open(caminho)
    except Exception as e:
        if re.search(r"password|encrypt", "%s %s %r" % (e.__class__.__name__, e, getattr(e, "__context__", None)), re.I):
            raise ValueError("PDF protegido por senha: gere a ficha de novo no SIAPEN, sem proteção") from e
        raise
    parcial = []
    with pdf:
        pags = [p.extract_text() or "" for p in pdf.pages]
        if not "".join(pags).strip():
            raise ValueError("PDF sem texto (digitalizado ou imagem): gere o PDF direto do SEEU/SIAPEN, não escaneado")
        if not e_ficha("\n".join(pags)):
            raise ValueError("não é uma Ficha Disciplinar do SIAPEN")
        dp_chars = _seguro(parcial, "cabeçalho (data da prisão pela posição)", lambda: _data_prisao_chars(pdf.pages[0]) if pdf.pages else "")
        vis, ocultas = [], []
        for k, p in enumerate(pdf.pages):
            try:
                v, o = _pagina_historico(p, k)
            except Exception as e:
                parcial.append("página %d: falha na separação do histórico (%s) - lido o texto corrido da página" % (k + 1, rs._falha(e)))
                v, o = pags[k], []
            vis.append(rs.sem_linhas_navegador(v)[0])
            ocultas += o
    return _extrair_texto(caminho, pags, vis, ocultas, dp_chars, parcial)


def _seguro(parcial, rotulo, fn, padrao=""):
    return rs._seguro(parcial, rotulo, fn, padrao)


def _extrair_texto(caminho, pags, vis, ocultas=(), dp_chars="", parcial=None):
    """Ficha a partir do texto: pags = texto de cada página; vis = texto visível de cada página (sem rodapé e histórico oculto)."""
    parcial = list(parcial or [])
    t = _limpar("\n".join(vis))
    f = {"arquivo": caminho, "tipo": "ficha_disciplinar", "_versao_extracao": VERSAO_EXTRACAO}
    m_hist = re.search(r"HISTÓRICO", t) or re.search(r"HISTORICO", t) or re.search(r"(?i)\bhist[óo]rico\b", t)
    if m_hist is None:
        parcial.append("título \"HISTÓRICO\" não encontrado: cabeçalho e histórico lidos do texto inteiro - conferir")
    cab = t[:m_hist.start()] if m_hist else t
    S = lambda rot, fn, padrao="": _seguro(parcial, "cabeçalho (%s)" % rot, fn, padrao)  # noqa: E731
    f["nome"] = S("nome", lambda: (re.search(r"Nome:\s*(.+?)\s+RGI:", cab) or [None, ""])[1].strip() if re.search(r"Nome:\s*(.+?)\s+RGI:", cab) else "")
    f["rgi"] = S("RGI", lambda: (re.search(r"RGI:\s*(\d+)", cab) or [None, ""])[1])
    f["cpf"] = S("CPF", lambda: cpf_cabecalho(cab))
    f["cpf_em_branco"] = S("CPF", lambda: not f["cpf"] and bool(re.search(r"CPF:\s*(?:CIN:|RG:|N/C\b|N[AÃ]O INFORMADO|$)", cab, re.M)), False)
    f["data_nascimento"] = S("data de nascimento", lambda: (re.search(r"Data Nascimento:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1])
    # filiação "MÃE \\ PAI" (a mãe vem primeiro no SIAPEN): confronto de identidade com o nome da mãe do RSPE (homônimos)
    f["filiacao"] = S("filiação", lambda: filiacao_cabecalho(cab))
    f["nome_mae"] = S("filiação", lambda: re.split(r"\s*[\\/|]\s*", f["filiacao"])[0].strip() if f["filiacao"] else "")
    # o valor fica na mesma linha do rótulo: campo em branco não pega a linha seguinte ("Condenação:" vazio levava "Data Entrada: ...")
    f["artigo"] = S("artigo", lambda: (re.search(r"Artigo:[ \t]*(.*)", cab) or [None, ""])[1].strip())
    f["data_prisao"] = S("data da prisão", lambda: (re.search(r"Data Prisão:[ \t]*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
                         or dp_chars or data_prisao_cabecalho(cab))
    f["condenacao"] = S("condenação", lambda: (re.search(r"Condenação:[ \t]*(.*)", cab) or [None, ""])[1].strip())
    f["unidade"] = S("unidade", lambda: (re.search(r"Unidade Penal:[ \t]*(.*)", cab) or [None, ""])[1].strip())
    f["data_entrada"] = S("data de entrada", lambda: (re.search(r"Data Entrada:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1])
    # sexo biológico do cadastro do SIAPEN ("M"/"F"): concordância de gênero nos textos (registro do SAP, fundamentações).
    # Sem o campo, a unidade feminina basta; do nome nada se deduz

    def _sexo():
        msx = re.search(r"Sexo(?: Biol[óo]gico)?:\s*(Masculino|Feminino)", cab, re.I)
        return msx.group(1)[0].upper() if msx else ("F" if re.search(r"FEMININ", rs._sem_acento(f["unidade"]).upper()) else "")
    f["sexo"] = S("sexo", _sexo)

    def _conduta():
        mc = re.search(r"HIST[ÓO]RICO\s*-\s*CONDUTA:\s*([^\n]+)", t) or re.search(r"CONDUTA:\s*([A-ZÇÃÕÁÉÍÓÚÂÊÔ/ ]+)", t)
        return mc.group(1).strip() if mc else ""
    f["conduta"] = S("conduta", _conduta)
    f["data_impressao"] = S("data de impressão", lambda: (re.search(r"Impresso em (\d{2}/\d{2}/\d{4})", "\n".join(pags)) or [None, ""])[1])
    f["paginas"], f["paginas_sem_texto"] = len(pags), [i + 1 for i, x in enumerate(pags) if len(x.strip()) < 20]
    # também os números grafados sem pontos ou hífen ("00107745720158120001", "0052142-562009.8.12.0001") ou com ponto no lugar do
    # hífen ("0003115.29.2013.8.12.0013": separador [-.] em rs.RE_CNJ_SOLTO), no formato canônico
    autos = sorted(set(rs.processos_no_texto(t)))
    f["autos"] = autos

    # ---- eventos do histórico ----
    def _eventos():
        hist = t[m_hist.end():] if m_hist else t
        partes = RE_LINHA.split(hist)
        # lançamento sem data no SIAPEN ("- CONSELHO DISCIPLINAR: FOI CONCLUSO ...", logo abaixo do título do histórico): fica como
        # texto sem data (nenhuma data é atribuída), no início do histórico
        sem_data = re.match(r"\s*(?:-\s*CONDUTA:[^\n]*\n)?\s*-\s*(\S.*)$", partes[0].split("\n", 1)[1] if "\n" in partes[0] else "", re.S)
        evs = ([{"data": "", "texto": " ".join(sem_data.group(1).split())}] if sem_data else []) + \
            [{"data": partes[i], "texto": " ".join(partes[i + 1].split())} for i in range(1, len(partes) - 1, 2)]
        evs = _datar_sem_data(_dividir(evs))
        return [dict(e, d=_dp(e["data"])) for e in evs]
    eventos = _seguro(parcial, "histórico (lançamentos)", _eventos, [])
    f["eventos"] = [{k: v for k, v in e.items() if k != "d"} for e in eventos]
    # histórico antigo em 10 pt, cortado na impressão: guardado à parte, sem virar lançamento (uso a decidir)
    f["historico_oculto"] = list(ocultas)  # exibido como "histórico anterior" (historico_anterior), fora das contas
    f["versao_leitura"] = VERSAO_LEITURA
    try:
        r = derivar(f, eventos)
    except Exception as e:
        # a análise do histórico falhou: a ficha entra com o cabeçalho e os lançamentos, sem as conclusões tiradas deles
        parcial.append("análise do histórico com falha (%s): ficha guardada com o cabeçalho e os lançamentos, sem trabalho, estudo e "
                       "faltas apurados - enviar o arquivo para correção" % rs._falha(e))
        try:
            r = derivar(f, [])
            r["eventos"] = f["eventos"]
        except Exception:
            r = f
    if parcial:
        r["_leitura_parcial"] = parcial
    return r


# versão das regras de leitura dos eventos: a ficha guardada na base com versão anterior é relida a partir dos eventos ao abrir
# (9: atestados "PROTOCOLADO ... REMIÇÃO totalizou", dias por extenso, "ias", "228T 76R", substituição "pelo nº X"; faltas antigas;
# 10: sublançamentos "dd/mm/aa... Nesta data/FOI/DEU ENTRADA", faltas em texto livre (PAD, isolamento, erros de digitação, PADIC por
# número, instauração), "LEI Nº 7.210", trabalho externo pela empresa, estudo encerrado na saída da unidade, isolamentos, dias só por
# extenso entre parênteses, atestado sem dias nem período; 11: leitura por ciclo sem mês, mudança de cela por sanção na lista de
# isolamentos, vínculos de trabalho do mesmo dia numa linha, "continua exercendo/cadastrado" como continuidade do vínculo - só exibição;
# 12: vínculos simultâneos - o setor encerrado só pelo início de outro vai até a sua baixa, sem lacuna falsa -, setor vazio ("no setor
# de trabalho , conforme documento"), fim de isolamento fora da lista de isolamentos, período do atestado "com data inicial em d e
# final em d", "início em d e término em d", "de (d) a (d)", setor começando por algarismo ou com apóstrofo, trecho do ATP sem "DATA";
# 13: sublançamento só com verbo após a data e fora de período (os demais, trecho sem data "a conferir"), lançamento sem data no
# SIAPEN datado pela única data citada no texto, autorização/termo de compromisso de trabalho externo "a conferir", falta só pela
# ciência marcada (data do fato desconhecida))
# 14: certidões de frequência escolar peticionadas, todos os meses dos cursos de qualificação e os autos citados nos documentos de estudo
# 15: trabalho escrito em texto livre também na lista de trabalho (início, fim, remanejamento, "deixa de trabalhar como X e passa a Y",
# "volta a trabalhar", "começou a trabalhar como X"), saída da unidade nas fichas antigas ("SAÍDA DA CPAIG", "transferido para",
# entrada em outra unidade, soltura) e não a saída por duplicidade de registros nem a saída temporária, "tornar sem efeito o
# lançamento do dia d", "desconsiderar a função X", "Liberação do Setor de Trabalho" sem baixa no dia, o vínculo simultâneo só quando
# o outro setor acabou antes da baixa tardia (não a baixa "saída do presídio"), nomes de setor sem "nesta UP", "CI nº ...", "sendo",
# "E" e "ATIVIDADE EXTERNA NA"; sinônimos e palavras próprias no singular)
VERSAO_LEITURA = 15
# versão da extração do PDF (camada de caracteres): a mesma ficha extraída por versão anterior é extraída de novo ao reimportar
VERSAO_EXTRACAO = 2


def _limpar_evento(txt):
    """Tira do texto do evento o cabeçalho de página que a leitura antiga deixou grudado ("RSS (8002969) em: 02/10/2026")."""
    return re.sub(r"\s*\b[A-Z0-9]{2,12}\s*\(\d{5,}\)\s*em:\s*\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?", "", txt or "").strip()


# verbo logo depois da data do sublançamento ("Em 11/03/04 Nesta data iniciou", "Foi alojado", "Tomou ciência", "isolado", "evadiu")
_RE_VERBO_SUB = re.compile(r"^\W{0,4}(?:NESTA DATA|DEU|FOI|FORAM|TEVE|FEZ|INICI\w*|\w{2,}(?:OU|IU|EU|ADO|ADA|IDO|IDA|ADOS|IDOS|ARAM|IRAM)(?:-SE)?)\b")


def _sub_em_periodo(antes, depois):
    """A data está dentro de um período ("de 16/05/2019 a 16/07/2019", "no período de d a d"): não é fato próprio."""
    a = rs._sem_acento(antes[-40:]).upper()
    return bool(re.search(r"\b(?:A|ATE|E|DE|DESDE|ENTRE|PERIODO)\s*$", a)) or \
        bool(re.match(r"\s*(?:A|ATE|-)\s*(?:EM\s+)?\d{1,2}[/.]\d{1,2}[/.]\d{2,4}", rs._sem_acento(depois[:30]).upper()))


def _dividir(eventos):
    """Lançamentos grudados no texto de outro: data em linha própria seguida de "-" sem texto na mesma linha ("12.12.2017 -\ntexto")
    e sublançamentos das fichas antigas ("... Em 11/03/04 Nesta data iniciou trabalho ..."), cada um com a sua data. Lançamento
    vazio sai; o sublançamento entra na ordem cronológica. O sublançamento "Em dd/mm/aa" só é fato próprio com data completa e
    válida seguida de verbo e fora de um período ("de ... a ..."); dentro de um período, não se divide; sem verbo (ou com data
    inválida), vira trecho sem data "a conferir" (a_conferir), logo depois do lançamento, sem entrar nas contas."""
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
            pos = [m for m in re.finditer(r"(?:^|(?<=[\s.;,]))Em (\d{2})/(\d{2})/(\d{2})(?![\d/])", t)
                   if not _sub_em_periodo(t[:m.start()], t[m.end():])]
            # "... Corumbá/MS. 04/09/08... Nesta data foi Preso", "... ARTESANATO. 10/03/09 FOI POSTO EM LIBERDADE", "18/03/17 DEU ENTRADA":
            # sublançamento só depois do fim de uma frase e com o verbo logo após a data (não "datada de d, foi", "no dia d foi")
            d0 = _dp(d)
            for m in re.finditer(r"(?<=[.;])\s+(\d{2})/(\d{2})/(\d{2}|\d{4})(?:\s*\.{1,3}\s*|\s+)(?=Nesta data|NESTA DATA|nesta data|FOI\b|foi\b|DEU ENTRADA)", t):
                aa = int(m.group(3))
                aa = aa + (2000 if aa < 70 else 1900) if aa < 100 else aa
                ds_ = _dp("%s.%s.%d" % (m.group(1), m.group(2), aa))
                if ds_ and (not d0 or ds_ >= d0) and not _sub_em_periodo("", t[m.end():]):
                    pos.append(m)
            pos.sort(key=lambda m: m.start())
            pedacos = [(d, t[:pos[0].start()] if pos else t)]
            for j, m in enumerate(pos):
                aa = int(m.group(3))
                aa = aa + (2000 if aa < 70 else 1900) if aa < 100 else aa
                ds = "%s.%s.%d" % (m.group(1), m.group(2), aa)
                # data completa e válida seguida de verbo: fato próprio; senão, trecho sem data a conferir
                ok = bool(_dp(ds)) and bool(_RE_VERBO_SUB.search(rs._sem_acento(t[m.end():m.end() + 40]).upper()))
                pedacos.append((ds if ok else "", t[m.start():pos[j + 1].start() if j + 1 < len(pos) else len(t)]))
            for j, (dd, tt) in enumerate(pedacos):
                tt = tt.strip()
                if tt:
                    ev = dict(e, data=dd, texto=tt) if (k or j) else dict(e, texto=tt)
                    if j and not dd:
                        ev["a_conferir"] = True
                        ev.pop("data_do_texto", None)
                        out.append(ev)  # sem data: fica junto do lançamento de onde saiu
                        continue
                    if j:
                        ev.pop("a_conferir", None)
                    (subs if j else out).append(ev)
    for ev in subs:  # sublançamento: antes do primeiro lançamento posterior a ele
        dv = _dp(ev["data"]) or date.min
        i = next((i for i, x in enumerate(out) if (_dp(x["data"]) or date.min) > dv), len(out))
        out.insert(i, ev)
    return out


def _data_citada(txt):
    """Única data citada no texto ("fato ocorrido em 05/10/2023", "alvará de soltura em 16/02/2016"), no formato da ficha; "" se
    não houver nenhuma ou houver duas ou mais diferentes (nunca a data do lançamento seguinte)."""
    ds = set()
    for m in re.finditer(r"(?<![\d/.])(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})(?![\d/.])", txt or ""):
        aa = int(m.group(3))
        aa = aa + (2000 if aa < 70 else 1900) if aa < 100 else aa
        d = _dp("%02d.%02d.%d" % (int(m.group(1)), int(m.group(2)), aa))
        if not d:
            return ""  # data ilegível ou inválida no texto: não se escolhe outra
        ds.add(d)
    return next(iter(ds)).strftime("%d.%m.%Y") if len(ds) == 1 else ""


def _datar_sem_data(evs):
    """Lançamento sem data no SIAPEN (não o trecho "a conferir" de _dividir): recebe a data citada no texto quando ela é única e
    inequívoca (data_do_texto) e entra na ordem cronológica; com nenhuma ou duas ou mais datas, segue só exibido, sem data."""
    out, novos = [], []
    for e in evs:
        if not (e.get("data") or "").strip() and not e.get("a_conferir") and not e.get("data_do_texto"):
            dc = _data_citada(e.get("texto"))
            if dc:
                novos.append(dict(e, data=dc, data_do_texto=True))
                continue
        out.append(e)
    for ev in novos:
        dv = _dp(ev["data"])
        i = next((i for i, x in enumerate(out) if (_dp(x.get("data") or "") or date.min) > dv), len(out))
        out.insert(i, ev)
    return out


def atualizar(f):
    """Ficha guardada com regras de leitura antigas: limpa os eventos e refaz trabalho, atestados, estudo, leitura e faltas
    a partir deles (sem reimportar o PDF). Devolve a própria ficha."""
    if not isinstance(f, dict) or f.get("versao_leitura") == VERSAO_LEITURA or not f.get("eventos"):
        return f
    for e in f["eventos"]:
        e["texto"] = _limpar_evento(e.get("texto"))
    # filiação gravada por leitura antiga com o "Nº Pront Saúde" colado ("...ALBUQUERQUENº Pront Saúde: PDIB - 52.281"): o valor
    # completo do arquivo, sem o campo vizinho, e o nome completo da mãe para a conferência de identidade ficha x RSPE
    if re.search(r"N[ºo°]\s*Pront", f.get("filiacao") or ""):
        f["filiacao"] = filiacao_cabecalho("Filiação: " + f["filiacao"])
        f["nome_mae"] = re.split(r"\s*[\\/|]\s*", f["filiacao"])[0].strip() if f["filiacao"] else ""
    f["eventos"] = _datar_sem_data(_dividir(f["eventos"]))
    eventos = [dict(e, d=_dp(e["data"])) for e in f["eventos"]]
    f["versao_leitura"] = VERSAO_LEITURA
    return derivar(f, eventos)


def _saida_trabalho(texto):
    """Lançamento que tira a pessoa da unidade e encerra o trabalho em curso: saída da unidade, transferência, evasão, soltura,
    livramento e, nas fichas antigas, a entrada em outra unidade ou a "SAÍDA DA CPAIG, motivo: ..." (rspe_remicao._saida_unidade).
    Não encerram: a mudança de cela, o atestado, o parecer (alvará consultado), a escolta, nem a saída da unidade por "duplicidade de
    registros" (correção de cadastro) ou por saída temporária (a pessoa volta)."""
    import rspe_remicao as rrm
    u = rrm._sa(texto)
    if re.match(r"\W*MUDANCA DE CELA", u) or re.search(r"\bATESTADO\b|\bATP\b|PARECER|AGUARDA", u) \
            or re.search(r"MOTIVO:\s*(?:DUPLICIDADE|SAIDA TEMPORARIA)", u) \
            or (re.search(r"ESCOLT", u) and not re.search(r"SAIDA DA UNIDADE PENAL|EVADI|EVASAO|\bFUGA\b", u)):
        return False
    return bool(rrm._saida_unidade(u, texto) or re.match(r"\W*SAIDA D[OA]S?\s+(?!CELA|SOLARIO|SETOR|TRABALHO|TEMPORARIA)\S", u))


def _desconsiderar(texto):
    """Correção do setor em texto livre ("Desconsiderar a função Faxina, interno trabalha na Prendebem"; "Atividade laboral correta
    X, desconsiderar Y"; "desconsiderar a função trabalho X, reconsiderar a função de trabalho Y"): (X anulado, Y que segue ou "")
    ou None. A baixa "desconsiderar o desligamento" é continuidade (outra regra)."""
    import rspe_remicao as rrm
    u = rrm._sa(texto)
    if re.match(r"\W*TRABALHO:", u):
        return None
    m = re.search(r"\bDESCONSIDERAR\s+(?:O\s+|A\s+)?(?:FUNCAO\s+(?:DE\s+)?(?:TRABALHO\s+)?|CADASTRO\s+(?:DE TRABALHO\s+)?(?:N[AO]\s+)?|SETOR\s+(?:DE\s+)?)?"
                  r"(?:EMPRESA\s+)?(?!O\b|A\b|DESLIGAMENTO|MOVIMENTACAO|ULTIMO|LANCAMENTO|BAIXA)([A-Z][A-Z/ ]{2,40}?)\s*(?=,|\.|;|$)", u)
    if not m:
        return None
    y = re.search(r"(?:CORRETA|RECONSIDERAR A FUNCAO DE TRABALHO|RECONSIDERAR A FUNCAO DE|INTERNO TRABALH[OA]|TRABALHA N[AO])\s*:?\s+"
                  r"(?:N[AO]\s+)?(?:EMPRESA\s+)?([A-Z][A-Z/ ]{2,40}?)\s*(?=,|\.|;|$|\bDESCONSIDERAR\b)", u)
    return m.group(1).strip(), (y.group(1).strip() if y else "")


def _nome_livre(nome):
    """Nome do setor lido em texto livre, sem o que não é nome ("ATIVIDADE EXTERNA NA EMPREITEIRA X" -> "EMPREITEIRA X")."""
    n = re.sub(r"^(?:A |O )?(?:ATIVIDADE|TRABALHO)(?: LABORAL)?\s+(?:EXTERNA|INTERNA|EXTERNO|INTERNO)\s*(?:-\s*|/\s*|N[AO]\s+|JUNTO A[O]?\s+)(?=\w{3})",
               "", nome or "")
    return n.strip(" ,.;:-") or (nome or "")


def _setor_igual(a, b):
    """Mesmo setor com outra grafia ("IPCG ARTESANATO" x "SETOR DE ARTESANATO"; "Serviços Gerais" x "Serviço Gerais")."""
    import rspe_remicao as rrm
    return bool(a and b) and (rrm.palavra_comum(a, b) or rrm.setor_parecido(rrm.setor_chave(a)[0], rrm.setor_chave(b)[0]))


def _trecho_original(texto, trecho):
    """O trecho (lido no texto sem acento, maiúsculo) como está escrito no lançamento, em maiúsculas e com os acentos."""
    import rspe_remicao as rrm
    sa, up = rrm._sa(texto), (texto or "").upper()
    i = sa.find(trecho)
    return up[i:i + len(trecho)].strip(" ,.") if i >= 0 and len(sa) == len(up) else trecho.strip(" ,.")


def _trabalho_livre(texto):
    """Início ou fim de trabalho escrito em texto livre (fichas antigas e redações próprias das unidades: "passa a trabalhar na
    empresa X", "remanejado para o setor X", "deixa de trabalhar como X e passa a desempenhar a função de Y", "desligado do
    trabalho"), pelas mesmas regras de rspe_remicao.vinculos. Devolve a lista de marcas, na ordem do texto: ("fim", setor ou "")
    e ("ini", setor, remanejamento); [] quando o lançamento não é de trabalho. O lançamento estruturado do SIAPEN ("TRABALHO:
    Iniciou/Deixa de trabalhar"), a mudança de cela, a continuidade ("continua cadastrado/trabalhando"), a atividade externa
    (_marcar_externo), o atestado, a escola/curso e a saída da unidade ficam com as suas próprias regras."""
    import rspe_remicao as rrm
    u = rrm._sa(texto)
    if re.match(r"\W*MUDANCA DE CELA", u):
        # "Mudança de cela ... motivo: deixou de trabalhar no setor X": fim de X
        mc = re.search(r"MOTIVO:[^,]*?DEIXA(?:R|U)? DE TRABALHAR\s+(?:N[AO]|DO|DA|EM)\s+(?:SETOR\s+(?:DE\s+|DA\s+|DO\s+)?)?([^,]+?)\s*(?:,|$)", u)
        return [("fim", mc.group(1))] if mc else []
    if re.match(r"\W*TRABALHO:\s*(?:INICIOU|DEIXA)", u) or re.search(r"\bCONTINUA\b|ATIVIDADE LABORAL EXTERNA", u) or rrm.RE_LIBERACAO.search(u):
        return []
    m = None if (re.search(r"\bCELA\b(?! LIVRE)|SOLARIO", u) and "SETOR" not in u) else next((x for x in (p.search(u) for p in rrm.RE_REMANEJ) if x), None)
    if m and m.group(1).strip():
        return [("fim", ""), ("ini", m.group(1).strip(), True)]
    m = next((x for x in (p.search(u) for p in rrm.RE_INI + rrm.RE_INI2) if x), None)
    if m and m.group(1).strip():
        return [("ini", m.group(1).strip(), False)]
    m = next((x for x in (p.search(u) for p in rrm.RE_FIM + rrm.RE_FIM2) if x), None)
    if m and m.group(1).strip():
        return [("fim", m.group(1).strip())]
    if rrm.RE_FIM_GERAL.search(u):
        return [("fim", "")]
    if rrm._NAO_TRAB.search(u) or re.search(r"\bATESTADO\b|\bATP\b", u):
        return []
    out = []
    fim_, ini_ = rrm.RE_FIM_RESERVA.search(u), rrm.RE_INI_RESERVA.search(u)
    if fim_ and (not ini_ or fim_.start() < ini_.start()):
        out.append(("fim", rrm._setor_livre(u[:ini_.start()] if ini_ else u)))
    if ini_:
        rem = "REMANEJAD" in ini_.group(0)
        nome = rrm._setor_livre(u[ini_.start():], rem)
        if nome:
            out += ([("fim", "")] if rem else []) + [("ini", nome, rem)]
    return out


def _marcar_externo(trabalho, eventos, ext):
    """Trabalho externo (inciso XI dos decretos): o lançamento "INICIA ATIVIDADE LABORAL EXTERNA NA EMPRESA X" marca o vínculo da
    mesma empresa (pelo nome, venha o "TRABALHO: Iniciou ..." antes ou depois no mesmo dia); sem vínculo da empresa iniciado até 3
    dias de diferença, o próprio lançamento abre o período externo (até o fim do trabalho seguinte registrado, a saída da unidade
    ou o início de outro trabalho). Setor chamado "TRABALHO EXTERNO" é externo."""
    import rspe_remicao as rrm
    for t in trabalho:
        if re.search(r"TRABALHO EXTERNO|\bEXTERNO\b", rs._sem_acento(t.get("setor") or "").upper()):
            t["externo"] = True
    novos = []
    for k, e in ext:
        u = rs._sem_acento(e["texto"]).upper()
        d = _dp(e["data"])
        if not d:
            continue
        me = re.search(r"EMPRESA\s+(.+?)(?:\s+CONVENIAD|\s+CUMPRINDO|\s+CONFORME|\s+UTILIZANDO|\s+COM\s|,|\.\s|$)", u) or \
            re.search(r"LABORAL EXTERNA(?:MENTE)?,?\s+(?:NA|NO|PARA A|PARA O|JUNTO A|JUNTO AO)\s+(?!EMPRESA)(.+?)(?:\s+CONVENIAD|\s+CUMPRINDO|\s+CONFORME|\s+UTILIZANDO|\s+COM\s|,|\.\s|$)", u)
        nome = me.group(1).strip() if me else ""

        def mesmo(t):
            return bool(nome) and (rrm.palavra_comum(t.get("setor") or "", nome) or rrm.setor_parecido(rrm.setor_chave(t.get("setor") or "")[0], rrm.setor_chave(nome)[0]))
        perto = [t for t in trabalho if _dp(t["inicio"]) and abs((_dp(t["inicio"]) - d).days) <= 3]
        um_dia = [t for t in perto if abs((_dp(t["inicio"]) - d).days) <= 1]
        # sem o nome igual: o único trabalho iniciado no mesmo dia (±1) é o externo (ex.: setor "XX-Desativado")
        alvo = [t for t in perto if mesmo(t)] or ([] if nome else perto[:1]) or (um_dia if len(um_dia) == 1 else [])
        if not alvo and not nome:
            alvo = [t for t in trabalho if _dp(t["inicio"]) and _dp(t["inicio"]) <= d <= (_dp(t.get("fim") or "") or date.max)][-1:]
        if alvo:
            for t in alvo:
                t["externo"] = True
                if nome:
                    t["empresa"] = nome
            continue
        # sem vínculo estruturado da empresa: o período externo vai do lançamento ao fim do trabalho (baixa, desligamento, saída,
        # evasão) ou ao início de outro trabalho registrado
        fim = None
        for e2 in eventos[k + 1:]:
            u2 = rs._sem_acento(e2["texto"]).upper()
            d2 = _dp(e2.get("data") or "")
            if not d2 or d2 < d:
                continue
            if re.search(r"DEIXA DE TRABALHAR|DESLIGAD|SAIDA DA UNIDADE PENAL|EVADI|EVASAO|\bFUGA\b|TRANSFERID", u2):
                fim = d2
                break
            if re.search(r"TRABALHO:\s*INICIOU|ATIVIDADE LABORAL EXTERNA|REMANEJAD", u2):
                fim = d2 - timedelta(days=1)
                break
        novos.append({"inicio": e["data"], "fim": fim.strftime("%d.%m.%Y") if fim else "", "setor": nome or "Trabalho externo", "externo": True,
                      "empresa": nome, "motivo_fim": "", "so_lancamento": True})
    if novos:
        trabalho.extend(novos)
        trabalho.sort(key=lambda t: _dp(t["inicio"]) or date.min)


_RE_EXTERNO_AUTORIZADO = re.compile(r"(?:FOI |FICA |ESTA |SENDO )?AUTORIZAD[OA]\W+(?:A\s+|O\s+|PARA\s+(?:O\s+)?|A REALIZAR\s+(?:O\s+)?)?TRABALHO EXTERNO|"
                                    r"AUTORIZACAO\W+(?:DE\s+|PARA\s+|DO\s+)?(?:O\s+)?TRABALHO EXTERNO|TERMO DE COMPROMISSO\b.{0,400}?TRABALHO EXTERNO")


def _juntar_mesmo_dia(trabalho):
    """Vínculos abertos no mesmo dia com nomes diferentes ("Iniciou ... FAXINA" e "Iniciou ... MARMITEIRO" na mesma data): o primeiro
    acaba no próprio dia (o segundo início o encerra) e vira uma linha só, com os dois nomes ("FAXINA / MARMITEIRO"). Só a lista
    exibida: o período é o do vínculo que segue, que já contém o do primeiro; não junta trabalho externo com interno nem o período
    externo aberto só pelo lançamento (inciso XI dos decretos)."""
    out = []
    for t in trabalho:
        p = out[-1] if out else None
        if p and p["inicio"] == t["inicio"] and (p.get("fim") or "") == p["inicio"] and not p.get("so_lancamento") and not t.get("so_lancamento") \
                and bool(p.get("externo")) == bool(t.get("externo")) and re.sub(r"\W", "", p["setor"].upper()) != re.sub(r"\W", "", t["setor"].upper()):
            t = dict(t)
            t["setores"] = list(dict.fromkeys((p.get("setores") or [p["setor"]]) + [t["setor"]]))
            t["setor"] = " / ".join(t["setores"])
            if p.get("empresa") and t.get("empresa") and p["empresa"] != t["empresa"]:
                t["empresa"] = p["empresa"] + " / " + t["empresa"]
            if p.get("jornada") and not t.get("jornada"):
                t["jornada"] = p["jornada"]
            out[-1] = t
        else:
            out.append(t)
    return out


def _separar_mesmo_dia(trabalho, eventos):
    """(7.14.2) Vínculos abertos no mesmo dia em setores DIFERENTES não são duplicados: quando a linha juntada ("POLIGONAL / SERRALHERIA")
    termina pela baixa só do último setor (com motivo próprio, não a saída da unidade) e os outros setores não têm baixa na ficha, eles
    seguem - até o início do trabalho seguinte, a saída da unidade ou, sem nenhum dos dois, em curso. Só é duplicado o mesmo setor."""
    import rspe_remicao as rrm
    out = list(trabalho)
    for t in list(trabalho):
        if len(t.get("setores") or []) < 2 or not t.get("fim") or not t.get("motivo_fim") \
                or t.get("texto_livre") or re.search(r"SAIDA|TRANSFER|EVAS|DESLIG|LIBERA|DUPLICIDADE|DESCONSIDER|A?DEQUACAO|"
                                                     r"OUTRA ATIVIDADE", rs._sem_acento(t["motivo_fim"]).upper()):
            continue
        ti, tf = _dp(t["inicio"]), _dp(t["fim"])
        pal_ = lambda x: set(re.findall(r"[A-Z0-9]{3,}", rs._sem_acento(x or "").upper()))
        mesmo_ = lambda a_, b_: (_setor_igual(a_, b_) or rrm._nome_confere(a_, b_) or rrm._nome_confere(b_, a_)
                                 or bool(pal_(a_)) and bool(pal_(b_)) and (pal_(a_) <= pal_(b_) or pal_(b_) <= pal_(a_)))
        ult = t["setores"][-1]
        if any(mesmo_(s, ult) for s in t["setores"][:-1]):
            continue  # nomes do mesmo setor (lançamento estruturado e outro nome): duplicado
        resto = [s for s in t["setores"][:-1] if not any(
            e["d"] and ti and e["d"] >= ti and re.match(r"\s*TRABALHO:\s*DEIXA DE TRABALHAR", e["texto"], re.I) and mesmo_(s, re.sub(
                r"(?i).*NO SETOR DE TRABALHO\s*", "", e["texto"]).split(",")[0]) for e in eventos)]
        if not resto or not ti or not tf:
            continue
        prox = [_dp(x["inicio"]) for x in trabalho if x is not t and _dp(x["inicio"]) and _dp(x["inicio"]) > ti]
        sai = [e["d"] for e in eventos if e["d"] and e["d"] > ti and _saida_trabalho(e["texto"])]
        fim_r = min(prox + sai) if (prox or sai) else None
        if fim_r and fim_r <= tf:
            continue  # os outros setores não vão além da baixa do último: nada a separar
        k = out.index(t)
        a = dict(t, setor=ult, setores=[ult])
        b = dict(t, setor=" / ".join(resto), setores=resto, fim=fim_r.strftime("%d.%m.%Y") if fim_r else "",
                 motivo_fim=("início de outra atividade" if fim_r in prox else "saída/evasão/transferência") if fim_r else "")
        if not fim_r:
            b.pop("motivo_fim", None)
        for x in (a, b):
            if len(x["setores"]) < 2:
                x.pop("setores")
        out[k:k + 1] = [b, a]
    return out


def _autos_citados(us):
    """Número CNJ citado no texto ("nos Autos Nº 6001397-76.2023.8.12.0001" ou "Nº60013977620238120001"), só os dígitos; '' sem número."""
    m = re.search(r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}", us or "")
    return re.sub(r"\D", "", m.group(0)) if m else ""


def derivar(f, eventos):
    """Campos da ficha que vêm dos eventos do histórico (trabalho, atestados, exames, leitura, faltas, estudo)."""

    # ---- trabalho ----
    import rspe_remicao as rrm

    def _ler_trabalho(continuidade):
        trabalho, aberto, baixas_orfas, ext, usou = [], None, [], [], False
        # datas em que o trabalho em curso se encerra para a leitura da remição (rspe_remicao.vinculos): saída da unidade, evasão,
        # transferência, desligamento ou afastamento sem setor, remanejamento e "Liberação do Setor de Trabalho" sem baixa no mesmo
        # dia - o vínculo encerrado pelo início de outro setor não é reaberto por cima delas
        baixa_dia = {e["data"] for e in eventos if re.match(r"\s*TRABALHO:\s*DEIXA DE TRABALHAR", e["texto"], re.I)}
        cortes = []
        for e in eventos:
            ua = rs._sem_acento(e["texto"]).upper()
            if not e["d"] or re.match(r"\s*TRABALHO:", ua):
                continue
            cela = ua.startswith("MUDANCA DE CELA")
            mf = None if cela else next((x for x in (p_.search(ua) for p_ in rrm.RE_FIM2) if x), None)
            if rrm.RE_LIBERACAO.search(ua):
                if e["data"] not in baixa_dia:
                    cortes.append((e["d"], None))
            elif _saida_trabalho(e["texto"]):
                cortes.append((e["d"], None))
            elif mf and mf.group(1).strip():
                cortes.append((e["d"], mf.group(1).strip()))  # desligamento de um setor nomeado: só encerra esse setor
            elif (re.search(r"DESLIGAD[OA]", ua) and re.search(r"TRABALHO|LABORA|ATIVIDADE", ua)) \
                    or (not cela and (rrm.RE_FIM_GERAL.search(ua) or re.search(r"\bREMANEJAD", ua))):
                cortes.append((e["d"], None))
            else:
                cortes += [(e["d"], mk[1] or None) for mk in _trabalho_livre(e["texto"]) if mk[0] == "fim"]

        def _corta(v, de, ate):
            # algum encerramento geral (ou do próprio setor) entre o fim inferido do vínculo (inclusive) e a baixa
            for c, nome in cortes:
                if de <= c < ate and (nome is None or rrm.palavra_comum(v["setor"], nome)
                                      or rrm.mesmo_setor(rrm.setor_chave(v["setor"])[0], rrm.setor_chave(nome)[0])):
                    return True
            return False
        # "tornar sem efeito o lançamento do dia d, referente ao setor de trabalho": os lançamentos de trabalho daquele dia não contam
        anulados = {m.group(1) for m in (rrm.RE_SEM_EFEITO.search(rs._sem_acento(e["texto"]).upper()) for e in eventos) if m}
        anulados = {_dp(x.replace("/", ".")) or rrm._dt(x) for x in anulados} - {None}
        for k_ev, e in enumerate(eventos):
            u = e["texto"].upper()
            if e["d"] in anulados and re.search(r"TRABALH|LABORA|SETOR", rs._sem_acento(u)) and not rrm.RE_SEM_EFEITO.search(rs._sem_acento(u)):
                continue
            # "desconsiderar a função X[, (trabalha / correta / reconsiderar a função) Y]": o vínculo de X aberto naquele dia não
            # existiu; o de Y segue (reaberto se a baixa dele foi no mesmo dia)
            mdx = _desconsiderar(e["texto"])
            # (com uma baixa posterior do próprio X por motivo de trabalho - "improdutividade", "mudança de atividade" - o SIAPEN
            # manteve o vínculo de X: a anotação não se sobrepõe a ele e nada muda)
            if mdx and any(e2["d"] and e["d"] and e2["d"] > e["d"] and _setor_igual(m2.group(1), mdx[0])
                           and not re.search(r"A?DEQUA|DESCONSIDER|DUPLICIDADE", rs._sem_acento(m2.group(2)).upper())
                           for e2 in eventos[k_ev + 1:]
                           for m2 in [re.search(r"TRABALHO:\s*DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.*?)(?:,\s*CONFORME.*?)?(?:MOTIVO:(.*))?$",
                                                e2["texto"].upper())] if m2):
                mdx = None
            if mdx:
                x_, y_ = mdx
                if aberto and aberto["inicio"] == e["data"] and _setor_igual(aberto["setor"], x_):
                    aberto = None
                trabalho[:] = [t for t in trabalho if not (t["inicio"] == e["data"] and _setor_igual(t["setor"], x_))]
                if y_ and not (aberto and _setor_igual(aberto["setor"], y_)):
                    v = next((t for t in reversed(trabalho) if t.get("fim") == e["data"] and _setor_igual(t["setor"], y_)), None)
                    if aberto:
                        aberto["fim"] = aberto.get("fim") or e["data"]
                        aberto.setdefault("motivo_fim", "início de outra atividade")
                        trabalho.append(aberto)
                    if v:
                        trabalho.remove(v)
                        v["fim"] = ""
                        v.pop("motivo_fim", None)
                        aberto = v
                    else:
                        aberto = {"inicio": e["data"], "fim": "", "setor": _trecho_original(e["texto"], y_), "externo": False, "texto_livre": True}
                continue
            # "continua exercendo suas atividades no setor X", "continua cadastrado no setor X" ("desconsiderar o desligamento"),
            # "sem efeito, continua trabalhando na empresa X": o vínculo de X segue - não abre vínculo novo nem encerra; a baixa
            # de X no mesmo dia fica sem efeito (exibição; a conta da remição é a de rspe_remicao)
            mc = continuidade and re.search(r"\bCONTINUA\s+(?:EXERCENDO|CADASTRAD[OA]|TRABALHANDO)\b(.*)", rs._sem_acento(u))
            if mc:
                if aberto is None:
                    i_ = next((i for i in range(len(trabalho) - 1, -1, -1) if trabalho[i].get("fim") == e["data"]
                               and rrm.palavra_comum(trabalho[i]["setor"], mc.group(1))), None)
                    if i_ is not None:
                        v = trabalho.pop(i_)
                        # o mesmo setor encerrado no mesmo dia pelo "Iniciou" repetido: é o mesmo vínculo, que segue desde o início
                        j_ = next((j for j in range(len(trabalho) - 1, -1, -1) if trabalho[j].get("fim") == v["inicio"]
                                   and trabalho[j].get("motivo_fim") == "início de outra atividade"
                                   and re.sub(r"\W", "", trabalho[j]["setor"].upper()) == re.sub(r"\W", "", v["setor"].upper())), None)
                        if j_ is not None:
                            v = trabalho.pop(j_)
                        v["fim"] = ""
                        v.pop("motivo_fim", None)
                        v["continuidade"] = e["data"]
                        aberto, usou = v, True
                continue
            # (setor vazio - "no setor de trabalho , conforme documento" - fica vazio, não vira "CONFORME DOCUMENTO")
            m = re.search(r"TRABALHO:\s*INICIOU ATIVIDADE LABORAL,?\s*NO SETOR DE TRABALHO\s*(.*?)(?:,\s*CONFORME|$)", u)
            if m:
                if aberto and aberto.get("texto_livre") and aberto["inicio"] == e["data"] and _setor_igual(aberto["setor"], m.group(1)):
                    aberto = None  # o mesmo início lançado antes em texto livre: fica o registro do SIAPEN
                if aberto:
                    # o trabalho novo encerra o anterior (a ficha nem sempre registra o "deixa de trabalhar"); se a baixa do anterior
                    # vier depois, sem saída da unidade no meio, ele é reaberto até ela (vínculos simultâneos - abaixo)
                    aberto["fim"] = aberto.get("fim") or e["data"]
                    aberto.setdefault("motivo_fim", "início de outra atividade")
                    trabalho.append(aberto)
                aberto = {"inicio": e["data"], "fim": "", "setor": m.group(1).strip(" ,."), "externo": False}
                continue
            m = re.search(r"TRABALHO:\s*DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.*?)(?:,\s*CONFORME|$)", u)
            if m:
                setor_fim = re.sub(r"\W", "", m.group(1))
                mm = re.search(r"MOTIVO:\s*(.+)$", u)
                motivo = (mm.group(1).strip(" .") if mm else "")
                d_ = _dp(e["data"])
                # baixa "desconsiderar o cadastro/lançamento" do setor aberto no próprio dia: o vínculo não existiu
                if re.search(r"DESCONSIDER", rs._sem_acento(motivo).upper()) and aberto and aberto["inicio"] == e["data"] \
                        and re.sub(r"\W", "", aberto["setor"].upper())[:12] == setor_fim[:12]:
                    aberto = None
                    continue
                # só encerra o trabalho do mesmo setor (a baixa de um setor antigo não encerra o atual)
                # (o vínculo aberto em texto livre com outra grafia do setor - "Montagem de Prendedores Prendebem" x "PRENDEBEM/PDIB" -
                # é o mesmo setor: a baixa estruturada o encerra)
                if aberto and (re.sub(r"\W", "", aberto["setor"].upper())[:12] == setor_fim[:12]
                               or (aberto.get("texto_livre") and setor_fim and _setor_igual(aberto["setor"], m.group(1)))):
                    aberto["fim"] = e["data"]
                    aberto["motivo_fim"] = motivo
                    trabalho.append(aberto)
                    aberto = None
                    continue
                ult = [t for t in trabalho if re.sub(r"\W", "", t["setor"].upper())[:12] == setor_fim[:12]]
                v = ult[-1] if ult else None
                fv = _dp(v.get("fim") or "") if v else None
                if v and v.get("fim_livre") and v.get("fim") == e["data"]:
                    v["motivo_fim"] = motivo or v.get("motivo_fim", "")  # já encerrado no dia pelo lançamento em texto livre
                    continue
                # (a baixa por "adequação do mapa do SIAPEN" é correção de cadastro - em geral do registro duplicado do mesmo dia -, não
                # prova que o setor seguiu: não reabre)
                # (7.14) só quando o outro setor já tinha acabado antes dessa baixa: com o outro ainda em curso, ou com a baixa lançada
                # na saída da unidade ("motivo: saída do presídio"), é registro tardio - nos atestados do corpus, o setor X acaba quando o
                # outro começa
                if v and v.get("motivo_fim") == "início de outra atividade" and fv and fv == d_:
                    v["motivo_fim"] = motivo  # a baixa no próprio dia em que o outro começou é só a baixa dele: registra o motivo
                    continue
                outros_ = [t for t in trabalho + ([aberto] if aberto else []) if t is not v and _dp(t["inicio"]) and fv and _dp(t["inicio"]) >= fv]
                if v and v.get("motivo_fim") == "início de outra atividade" and fv and d_ and fv <= d_ \
                        and not re.search(r"A?DEQUACAO DO MAPA|SAIDA D[OA] (?:PRESIDIO|UNIDADE)|SAIU DA UNIDADE|TRANSFERENCIA", rs._sem_acento(motivo).upper()) \
                        and all(_dp(t.get("fim") or "") and _dp(t["fim"]) < d_ for t in outros_) \
                        and not _corta(v, fv, d_):
                    # vínculo simultâneo: o setor X foi encerrado só pelo início de outro setor e a baixa de X vem depois, sem saída,
                    # evasão, transferência, desligamento, remanejamento ou liberação no meio - os dois setores correram juntos; X vai
                    # até a sua baixa (sem a lacuna falsa entre o início do outro e a baixa). Só a lista exibida: a remição
                    # (rspe_remicao.vinculos, que já lê os setores em paralelo) conta os dias como conjunto, sem dobrar o dia
                    # (a baixa no próprio dia em que o outro começou é só a baixa dele: registra o motivo)
                    if d_ > fv:
                        v["fim"] = e["data"]
                        v["simultaneo"] = True
                    v["motivo_fim"] = motivo
                    continue
                if not setor_fim and aberto:
                    # baixa sem setor: encerra o único vínculo aberto
                    aberto["fim"] = e["data"]
                    aberto["motivo_fim"] = motivo
                    trabalho.append(aberto)
                    aberto = None
                    continue
                # baixa de um setor sem trabalho aberto: a unidade o mantinha alocado sem registrar o início
                baixas_orfas.append({"data": e["data"], "setor": m.group(1).strip(" ,."),
                                     "ultimo_inicio": v["inicio"] if v else "", "ultimo_fim": v.get("fim", "") if v else ""})
                continue
            # trabalho em texto livre (fichas antigas e redações das unidades - _trabalho_livre): o início abre o vínculo e encerra o
            # anterior, como o "Iniciou" do SIAPEN; o mesmo setor de novo, com o vínculo dele aberto, é o mesmo vínculo; o fim com setor
            # só encerra esse setor, sem setor encerra o vínculo aberto. A saída da unidade segue a regra própria (abaixo)
            saida_ev = _saida_trabalho(e["texto"])
            marcas = [] if saida_ev else _trabalho_livre(e["texto"])
            for mk in marcas:
                if mk[0] == "fim":
                    if aberto and (not mk[1] or _setor_igual(aberto["setor"], mk[1])):
                        aberto["fim"] = e["data"]
                        aberto["motivo_fim"] = "remanejado para outro setor" if len(marcas) > 1 and marcas[-1][0] == "ini" and marcas[-1][2] else "desligado"
                        aberto["fim_livre"] = True
                        trabalho.append(aberto)
                        aberto = None
                    continue
                nome = _nome_livre(_trecho_original(e["texto"], mk[1]))
                if aberto and _setor_igual(aberto["setor"], nome):
                    continue  # o mesmo setor, com o vínculo dele aberto: é o mesmo vínculo
                if aberto:
                    aberto["fim"] = aberto.get("fim") or e["data"]
                    aberto.setdefault("motivo_fim", "início de outra atividade")
                    trabalho.append(aberto)
                aberto = {"inicio": e["data"], "fim": "", "setor": nome, "externo": False, "texto_livre": True}
            if marcas:
                continue
            # "Liberação do Setor de Trabalho" sem a baixa de um setor no mesmo dia: o trabalho em curso acaba (com a baixa, é só o
            # registro dela - o "motivo: desligado" da liberação não encerra o setor iniciado no mesmo dia)
            if rrm.RE_LIBERACAO.search(rs._sem_acento(u).strip()):
                if aberto and e["data"] not in baixa_dia:
                    aberto["fim"] = e["data"]
                    aberto["motivo_fim"] = "liberação do setor de trabalho"
                    trabalho.append(aberto)
                    aberto = None
                continue
            # desligamento em texto livre, evasão, saída ou transferência de unidade encerram o trabalho em curso
            # (entrada na unidade e início do trabalho no mesmo dia, em qualquer ordem: a entrada não encerra o trabalho que começa nela)
            if saida_ev and aberto and aberto["inicio"] == e["data"] and not re.match(r"\W*SA[ÍI]DA DA UNIDADE PENAL", u):
                saida_ev = False
            if (re.search(r"DESLIGAD[OA]", u) and re.search(r"TRABALHO|LABORA|ATIVIDADE", u)
                    or saida_ev):
                if aberto:
                    aberto["fim"] = e["data"]
                    aberto["motivo_fim"] = ("saída/evasão/transferência" if saida_ev else "desligado")
                    trabalho.append(aberto)
                    aberto = None
                    continue
            if re.search(r"ATIVIDADE LABORAL EXTERNA|ATIVIDADE LABORAL EXTERNAMENTE", u):
                ext.append((k_ev, e))
        if aberto:
            trabalho.append(aberto)
        for t in trabalho:
            t.pop("fim_livre", None)
        if usou:
            trabalho.sort(key=lambda t: _dp(t["inicio"]) or date.min)
        _marcar_externo(trabalho, eventos, ext)
        return trabalho, baixas_orfas, usou

    def _cobertura_externa(tr):
        # períodos de trabalho externo, unidos (o que complementar_decretos conta no inciso XI)
        out = []
        for a, b in sorted((_dp(t["inicio"]) or date.min, _dp(t.get("fim") or "") or date.max) for t in tr if t.get("externo")):
            if out and a <= out[-1][1] + timedelta(days=1):
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
        return out
    trabalho, baixas_orfas, usou = _ler_trabalho(True)
    if usou:
        # a continuidade é só leitura do vínculo: se mudasse um período de trabalho externo (art. 9º, XI, dos decretos), vale a
        # leitura sem ela
        t0, b0, _u = _ler_trabalho(False)
        if _cobertura_externa(t0) != _cobertura_externa(trabalho):
            trabalho, baixas_orfas = t0, b0
    # jornada de cada trabalho: a ficha às vezes registra a carga horária ("de segunda a sexta", "12x36") no início
    for t in trabalho:
        ti, tf = _dp(t["inicio"]), _dp(t.get("fim") or "")
        for e in eventos:
            if e["d"] and ti and ti - timedelta(days=3) <= e["d"] <= min(tf or date.max, ti + timedelta(days=30)):
                j = jornada_do_texto(e["texto"])
                if j:
                    t["jornada"] = j
                    break
    f["trabalho"] = _separar_mesmo_dia(_juntar_mesmo_dia(trabalho), eventos)
    f["baixas_sem_inicio"] = baixas_orfas
    # "foi autorizado o trabalho externo" e termo de compromisso de trabalho externo: início "a conferir" (inciso XI dos decretos),
    # sem contar como prestação efetiva. Ala/cela de semiaberto e prefixo de setor não bastam
    f["externo_a_conferir"] = [{"inicio": e["data"], "texto": e["texto"][:200]} for e in eventos if e["d"] and _RE_EXTERNO_AUTORIZADO.search(rs._sem_acento(e["texto"]).upper())
                               and not re.search(r"NAO (?:FOI |ESTA |FICA )?AUTORIZ|INDEFERI|NEGAD|REVOGAD|SUSPENS|CANCELAD|^\W*MUDANCA DE CELA", rs._sem_acento(e["texto"]).upper())]

    # ---- atestados de trabalho (dias trabalhados / remidos): a mesma leitura da conciliação da remição ----
    atest = []
    trab_p = [(_dp(t["inicio"]), _dp(t.get("fim") or "") or date.max) for t in f["trabalho"] if _dp(t["inicio"])]
    for a in rrm.atestados(eventos):
        ss = [x for x in a["segs"] if x["ini"] and x["fim"]]
        corr, ss0, ss = [], ss, []
        for x in ss0:
            # (7.14.2) trecho com o ano digitado errado (início 01/07/2023, fim 05/10/2022): o ano trocado que faz o trecho caber num
            # trabalho registrado na ficha - lido com o ano corrigido e marcado "ano corrigido · conferir"
            if x["ini"] > x["fim"]:
                for ini_, fim_ in ((x["ini"].replace(year=x["fim"].year) if not (x["ini"].month == 2 and x["ini"].day == 29) else None, x["fim"]),
                                   (x["ini"], x["fim"].replace(year=x["ini"].year) if not (x["fim"].month == 2 and x["fim"].day == 29) else None)):
                    if ini_ and fim_ and ini_ <= fim_ and any(ti <= ini_ + timedelta(days=3) and fim_ <= tf + timedelta(days=3) for ti, tf in trab_p):
                        corr.append("%s: %s a %s lido como %s a %s" % (x["setor"] or "trecho", rrm._f(x["ini"]), rrm._f(x["fim"]), rrm._f(ini_), rrm._f(fim_)))
                        x = dict(x, ini=ini_, fim=fim_)
                        break
            ss.append(x)
        atest.append({"ano_corrigido": "; ".join(corr), "data": a["emissao"].strftime("%d.%m.%Y"), "numero": a["numero"], "dias_trabalhados": a["trab"] or 0, "dias_remidos": a["rem"] or 0,
                      "periodo_inicio": rrm._f(min(x["ini"] for x in ss)) if ss else "", "periodo_fim": rrm._f(max(x["fim"] for x in ss)) if ss else "",
                      "empresa": ", ".join(dict.fromkeys(x["setor"] for x in a["segs"] if x["setor"])), "autos": a.get("autos", ""),
                      "trechos": [{"setor": x["setor"], "inicio": rrm._f(x["ini"]), "fim": rrm._f(x["fim"]), "rem": x.get("rem")} for x in ss] if len(ss) > 1 else []})
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
            cert = mx.group(1) == "ENCCEJA" and conclusao_certificada(u)
            exames.append({"exame": mx.group(1) + ((" " + mx.group(2)) if mx.group(2) else ""), "data": e["data"], "certificado": cert,
                           "ano": int(mx.group(2)) if mx.group(2) else None, "autos": _autos_citados(rs._sem_acento(u))})
    f["exames"] = exames
    # relatórios de leitura peticionados (remição pela leitura - Res. CNJ 391/2021, art. 5º: 4 dias por obra, até 12 obras por
    # ano): os meses citados em cada petição
    leituras, cursos_pet, certidoes = [], [], []
    for e in eventos:
        u = re.sub(r"\s+", " ", e["texto"].upper())
        us = rs._sem_acento(u)
        if re.search(r"PETICIONAD\w* (?:OS |O )?CURSOS? DE QUALIFICACAO", us):
            # todos os meses citados: "referentes aos meses 08,09,10 de 2024 e mês 02 de 2025" (o segundo grupo também conta)
            meses_c = []
            for mm in re.finditer(r"\bMES(?:ES)?\s+((?:\d{1,2}\s*(?:,|\bE\b)\s*)*\d{1,2})\s*DE\s+(\d{4})", us):
                meses_c += ["%02d/%s" % (int(x), mm.group(2)) for x in re.findall(r"\d{1,2}", mm.group(1)) if 1 <= int(x) <= 12]
            cursos_pet.append({"data": e["data"], "texto": e["texto"], "meses": list(dict.fromkeys(meses_c)), "autos": _autos_citados(us)})
            continue
        if re.search(r"CERTID[AO]+ DE FREQUENCIA ESCOLAR", us) and re.search(r"PETICION|PROTOCOL|JUNTAD|ENVIAD", us):
            # certidão de frequência escolar peticionada no SEEU ("referente ao 2º semestre de 2025"): a remição pelo estudo do semestre
            # costuma sair dias depois, com a referência no fim do semestre letivo
            ms = re.search(r"(\d)\s*(?:[ºª°O]|\W){0,2}\s*SEMESTRE\s+(?:DE\s+|LETIVO\s+(?:DE\s+)?)?(\d{4})", us)
            certidoes.append({"data": e["data"], "texto": e["texto"], "semestre": int(ms.group(1)) if ms and ms.group(1) in "12" else None,
                              "ano": int(ms.group(2)) if ms else None, "autos": _autos_citados(us)})
            continue
        # (7.14.1) e o certificado da "Jornada da Leitura no Cárcere" (projeto de leitura): documento de leitura sem o número de
        # obras no texto - fica a conferir, fora da conta
        if not re.search(r"RELATORIOS? DE LEITURA|RESENHA|REMICAO P(?:OR|ELA) LEITURA|JORNADA DA LEITURA", us):
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
        lt = {"data": e["data"], "meses": meses, "obras": obras, "texto": e["texto"], "oficio": mof.group(1) if mof else ""}
        mci = re.search(r"\bCICLO\s*N?\W{0,3}(\d{1,2}\s*/\s*\d{2,4})", us)
        if mci and not meses:
            # atestado por ciclo, sem mês ("Atestado de Remição por Leitura nº 71/2020 - CICLO nº 03/2020"): o lançamento fica no mês
            # do próprio atestado/protocolo (referência só para exibir; "meses" segue vazio e a conta segue 4 dias por obra)
            lt["ciclo"] = re.sub(r"\s+", "", mci.group(1))
            lt["ref_mes"] = e["d"].strftime("%m/%Y") if e.get("d") else ""
        leituras.append(lt)
    f["leituras"] = leituras
    f["cursos_peticionados"] = cursos_pet
    f["certidoes_estudo"] = certidoes
    f["dias_trabalhados_atestados"] = sum(a["dias_trabalhados"] for a in atest)
    f["dias_remidos_atestados"] = round(sum(a["dias_remidos"] for a in atest), 2)

    # ---- faltas disciplinares ----
    faltas, narrativas = [], []

    def _nat(us):
        mn = re.search(r"(?:FALTA|NATUREZA)\W*(?:DISCIPLINAR\W*)?(?:DE\s+NATUREZA\W*)?(GRAVE|MEDIA|LEVE)\b", us)
        return mn.group(1) if mn else ""
    _PROC_RES = r"(?:PROCESSO DISCIPLINAR|\bPADIC\b|\bPAD\b).*(?:SANCIONAD|CELA DISCIPLINAR|ISOLAMENTO|CONCLUIU|SUGERIU)"
    for e in eventos:
        us = _texto_falta(e["texto"])
        u = us
        if "CONSELHO DISCIPLINAR" not in u and "FALTA DISCIPLINAR" not in u and "FALTA GRAVE" not in u and \
                not re.search(r"FALTA (?:DISCIPLINAR )?DE NATUREZA|INSTAURAD\w* (?:A |S )?CDS|SANCIONADO ADMINISTRATIVAMENTE|RECONHECO A PRATICA|" + _PROC_RES, us):
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
        if (re.search(r"REGISTRO DE FALTA|LAN[ÇC]AMENTO DE FALTA|FALTA GRAVE", us) or re.search(_RE_RESULTADO, us) and (
                re.search(r"FALTA (?:DISCIPLINAR )?(?:DE NATUREZA|GRAVE|MEDIA|LEVE)|PRATICOU FALTA", us) or re.search(_PROC_RES, us))) \
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
                npad_ = num_padic(us)
                alvo = next((x for x in faltas if x["data_fato"].replace(".", "/") == dfr.replace(".", "/")), None) or \
                    next((x for x in faltas if npad_ and x.get("padic_num") == npad_), None)
                art = re.search(r"ART\.?\s*(50|52)\b", us)
                nat = _nat(us)
                # isolamento em cela disciplinar só se aplica à falta grave (LEP, art. 57, p. ú.)
                isol = bool(re.search(r"(?:SANCIONAD\w*|CONCLUIU|SUGERIU|DECISAO)\W.{0,80}(?:CELA DISCIPLINAR|ISOLAMENTO)|(?:CELA DISCIPLINAR|ISOLAMENTO).{0,40}SANCIONAD", us))
                if alvo is None:
                    alvo = {"data_registro": e["data"], "data_fato": dfr, "artigo": ("art. %s da LEP" % art.group(1)) if art else "",
                            "grave": bool(art) or "FALTA GRAVE" in us or nat == "GRAVE" or (isol and nat not in ("MEDIA", "LEVE")),
                            "texto": e["texto"], "padic": "", "resultado": ""}
                    if not (mf and _d(mf.group(1))):
                        # só a ciência do resultado: a data do fato é desconhecida (a da ciência é posterior)
                        alvo["data_fato_ciencia"], alvo["data_fato_obs"] = True, "data da ciência do resultado: a data do fato não consta da ficha"
                    faltas.append(alvo)
                elif e["texto"] not in alvo["texto"]:
                    alvo["texto"] += " | " + e["texto"]
                if npad_:
                    alvo["padic_num"] = npad_
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
            if not cometida and re.search(r"COMETIDA EM\s*\d{0,2}/+\d{0,2}/+\d{2,4}", u):
                # data do fato ilegível ("1//12/2009"): usada a do lançamento, com aviso
                faltas[-1]["data_fato_ciencia"], faltas[-1]["data_fato_obs"] = True, "data do fato ilegível na ficha: usada a do lançamento"
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
    # isolamento preventivo em cela disciplinar com PADIC em curso, sem a natureza da falta: o isolamento é sanção só da falta grave
    # (LEP, arts. 53, IV, 57, p. ú., e 60) - indício de falta grave, a apurar até o resultado do PADIC
    for x in faltas:
        ux = rs._sem_acento(x.get("texto") or "").upper()
        if not x.get("grave") and re.search(r"ISOLAD[OA]\s+PREVENTIV", ux) and (x.get("situacao") == "PADIC instaurado" or "PADIC" in ux):
            x["grave_indicio"] = True
    # andamento e resultado do PADIC / CD simplificada: casados com a falta pela data do fato ("referente ao fato ocorrido em",
    # "cometida em"), pelo número do PADIC ou, na instauração sem data, pela falta registrada mais próxima; vale o último resultado
    def _nd(x):
        return (x or "").replace(".", "/")

    _num_padic = num_padic
    for e in eventos:
        # erro de digitação na ficha antiga ("tomou ciência da decidsão do Conselho Disciplinar")
        u = _texto_falta(e["texto"])
        # a instauração do PADIC cita a falta ("REFERENTE A LANÇAMENTO DE FALTA DISCIPLINAR COMETIDA EM d") e é lida (nº do PADIC)
        if not re.search(r"CONSELHO DISCIPLINAR|APLICACAO DE SANCAO", u) or re.search(r"REGISTRO DE FALTA|ISOLADO", u) or \
                ("LANCAMENTO DE FALTA" in u and not re.match(r"CONSELHO DISCIPLINAR:\s*INSTAURACAO", u)):
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
            if instaura or not re.search(r"CIENCIA D[OA] (?:RESULTADO|DECISAO)|CONCLUSO|DECISAO DO (?:PRESIDENTE DO )?CONSELHO|APLICACAO DE SANCAO", u) or \
                    not re.search(r"SANCIONAD|COMETEU FALTA|IMPUTADO (?:N?O )?COMETIMENTO|PROPOSTA DE REGRESSAO|SANCAO DISCIPLINAR|ADVERTENCIA|REPREENSAO", u) or \
                    re.search(r"ABSOLVID|EXTINT|ARQUIVAD|PRESCRI|SANCIONADO PREVENTIVAMENTE|AGUARDA", u):
                continue
            mf = re.search(_RE_FATO_RES, u)
            dt = (m.group(1) or m.group(2)) if m else (mf.group(1) if mf and len(mf.group(1)) == 10 else e["data"])
            alvo = {"data_registro": e["data"], "data_fato": dt, "artigo": _artigo_falta(u), "grave": "FALTA GRAVE" in u or _nat(u) == "GRAVE",
                    "texto": e["texto"], "padic": "", "resultado": "", "situacao": "registrada"}
            if not m and not (mf and len(mf.group(1)) == 10):
                alvo["data_fato_ciencia"], alvo["data_fato_obs"] = True, "data da ciência do resultado: a data do fato não consta da ficha"
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
        if not re.search(r"CIENCIA DO RESULTADO|CONCLUSO|ARQUIVADO|EXTINTO|APLICACAO DE SANCAO|DECISAO DO (?:PRESIDENTE DO )?CONSELHO", u):
            continue
        if re.search(r"ABSOLVID", u):
            tipo = "absolvido"
        elif re.search(r"EXTINT|PRESCRI", u):
            # item 57 de 16/10: PADIC extinto ou arquivado por prescrição ("reconhecida a prescrição") não produz efeito disciplinar
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
    # o mesmo PADIC em duas faltas (ciência em texto livre com a data do fato diferente ou não reconhecida): uma falta só - fica a do
    # registro (a primeira), com o resultado que houver
    for x in list(faltas):
        if x not in faltas or not x.get("padic_num"):
            continue
        for y in [y for y in faltas if y is not x and y.get("padic_num") == x["padic_num"]]:
            if y["texto"] not in x["texto"]:
                x["texto"] += " | " + y["texto"]
            if not x.get("resultado") and y.get("resultado"):
                for k_ in ("resultado", "data_resultado", "resultado_tipo", "situacao", "natureza"):
                    if y.get(k_):
                        x[k_] = y[k_]
            x["grave"] = x["grave"] or (y["grave"] and not x.get("natureza"))
            x["artigo"] = x.get("artigo") or y.get("artigo")
            faltas.remove(y)
    faltas.sort(key=lambda x: _dp(x["data_fato"]) or _dp(x.get("data_registro") or "") or date.min)
    f["faltas"] = faltas

    # ---- outros marcos relevantes ----
    f["regressoes"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"REGRESS", e["texto"], re.I)]
    f["restabelecimentos"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"RESTABELEC", e["texto"], re.I)]
    f["recusa_trabalho"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"RECUSOU VAGA|RECUSA DE TRABALHO", e["texto"], re.I)]
    f["isolamentos"] = [e["data"] + " - " + e["texto"] + (" [indício de isolamento: mudança de cela por sanção - conferir a sanção]"
                                                          if _cela_por_sancao(e["texto"]) else "")
                        for e in eventos if _e_isolamento(e["texto"])]
    f["estudo"] = [e["data"] + " - " + e["texto"] for e in eventos if re.search(r"ESTUD|LEITURA|CURSO|ESCOLA", e["texto"], re.I) and "TRABALHO" not in e["texto"].upper()]
    f["estudo_cancelado_sem_matricula"] = []
    f["estudos"] = _estudos(eventos, f["estudo_cancelado_sem_matricula"])
    return f


# ---------------------------------------------------------------- confronto com o RSPE

def confrontar(r, f, hoje=None, manuais=None):
    """Compara ficha (f) com o registro do RSPE (r). Devolve lista de itens no formato da auditoria:
    {nivel, titulo, detalhe, fundamento}. A remição (comparação dos totais, documentos, trabalho sem atestado) fica na aba Ficha
    (comparativo): o RSPE não diz a origem de cada remição, e a Auditoria não liga remição a atestado."""
    itens = []
    if not f:
        return itens
    # 3b) falta grave anterior registrada na ficha x perda de dias remidos no RSPE (art. 127: sem desconto em duplicidade)
    itens.extend(_falta_anterior_x_perda(r, f))
    # 3c) cumprimento parado no RSPE x custódia na ficha
    itens.extend(_interrupcao_x_ficha(r, f))
    # 3d) progressão, regressão e livramento cumpridos na unidade e ausentes do RSPE
    itens.extend(_regime_x_ficha(r, f))
    # 3e) identidade, prisão, processos, pena, unidade x regime, fuga e conduta
    for fn in (_identidade_x_ficha, _prisao_x_ficha, _detracao_x_ficha, _soltura_x_ficha, _processos_x_ficha, _pena_x_ficha, _unidade_x_ficha, _fuga_x_ficha, _conduta_x_ficha,
               _historico_anterior_x_ficha, _faltas_outra_execucao_x_ficha):
        try:
            itens.extend(fn(r, f))
        except Exception as e:
            itens.append(_item_rf("verificar", "Ficha x RSPE: falha ao conferir (%s: %s)" % (fn.__name__.strip("_"), e), "", ""))
    for it in itens:
        it.pop("detalhe_", None)
        it["origem"] = "ficha"
        it["titulo"], it["detalhe"] = _br(it["titulo"]), _br(it.get("detalhe") or "")
    return itens


def leitura_parcial(f):
    """Leitura da ficha para o registro da importação: (observações, parcial). Campo que o próprio SIAPEN deixa em branco
    (ex.: "CPF:" vazio no cabeçalho) é observação, não leitura parcial."""
    out, parcial = [], False
    if f.get("_leitura_parcial"):
        out += list(f["_leitura_parcial"])
        parcial = True
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
        sem_data = sum(1 for e in evs if not (e.get("data") or "").strip())
        conf = sum(1 for e in evs if e.get("a_conferir"))
        dtx = [e for e in evs if e.get("data_do_texto")]
        if sem_data - conf:
            # o próprio SIAPEN imprime o lançamento sem data ("- CONSELHO DISCIPLINAR: ..."): guardado como texto, sem data atribuída
            out.append("%s sem data no SIAPEN (guardado como texto, sem data atribuída: o texto não cita uma data única)" % rs.pl(sem_data - conf, "lançamento", "lançamentos"))
        if dtx:
            out.append("%s sem data no SIAPEN datado pela única data citada no texto (%s) - conferir" % (
                rs.pl(len(dtx), "lançamento", "lançamentos"), ", ".join(_br(e["data"]) for e in dtx[:5])))
        if conf:
            # data dentro do texto de outro lançamento sem verbo logo depois (ou inválida): não vira fato próprio nem entra nas contas
            out.append("%s com data dentro de outro lançamento sem verbo logo após a data (não lido como fato próprio, sem data nas contas) - a conferir" %
                       rs.pl(conf, "trecho", "trechos"))
        if len(ds) + sem_data < len(evs):
            out.append("%d de %d registros do histórico sem data legível" % (len(evs) - len(ds) - sem_data, len(evs)))
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
    entradas = [(x, t) for x, t in dep if RE_ENTRADA.search(t)]
    # saída por determinação judicial ou para a domiciliar depois da última entrada e da última soltura: monitoramento e domiciliar
    # são cumprimento; destino incerto sem nova entrada, a conferir (nunca liberdade automática)
    jud = [(x, t, saida_judicial(t, ev, x)) for x, t in dep if RE_SAIDA_JUDICIAL.search(t)]
    jud = [(x, t, sj) for x, t, sj in jud if sj and sj[0] != "transferencia"]
    if jud and jud[-1][0] >= max([y for y, _ in livres[-1:] + entradas[-1:]] or [date.min]):
        x, _t, (tipo, dest) = jud[-1]
        return (None if tipo == "a_conferir" else True), _rotulo_saida_judicial(x, tipo, dest)
    if livres and (not entradas or livres[-1][0] > entradas[-1][0]):
        mm = re.search(r"MOTIVO:\s*([^,]+)", livres[-1][1], re.I)
        return False, "saída em %s (%s)" % (rs.fmt(livres[-1][0]), mm.group(1).strip().lower() if mm else _br(livres[-1][1])[:60])
    un = f.get("unidade") or ""
    if entradas:
        mu = re.search(r"UNIDADE PENAL:\s*([^,]+)", entradas[-1][1], re.I)
        un = (mu.group(1).strip() if mu else un)
        return True, "entrada em %s%s; último registro em %s" % (rs.fmt(entradas[-1][0]), (" - " + un) if un else "", rs.fmt(dep[-1][0]))
    return True, "registros na unidade%s até %s, sem saída em liberdade" % ((" " + un) if un else "", rs.fmt(dep[-1][0]))


# entrada em unidade: a estruturada ("Entrada na Unidade Penal: X, Procedente: Y"; "Entrada no Regime Semiaberto da Unidade Penal: X") e a das fichas antigas ("DEU ENTRADA NO IPCG",
# "ENTRADA NO EPJFC, PROCEDENTE DO DENAR")
RE_ENTRADA = re.compile(r"ENTRADA NA UNIDADE|DEU ENTRADA|^ENTRADA N[OA]\s+\S+.{0,40}?PROCEDENTE|^ENTRADA NO REGIME [\w-]+ DA UNIDADE PENAL", re.I)


RE_PENA_EXTINTA_FICHA = re.compile(r"PENA EXTINTA EM (\d{1,2}/\d{1,2}/\d{2,4})", re.I)


def extincao_outra_execucao(r, f, desde):
    """Custódia que começa em 'desde' e que, pela ficha, serviu a OUTRA execução: lançamento "PENA EXTINTA EM d ... AUTOS ... X" com
    X fora deste RSPE, sem soltura entre 'desde' e d. Esse tempo já foi usado naquela pena e não se detrai de novo: o cumprimento
    desta execução só começa no dia seguinte à última extinção. Devolve (d, autos) ou None."""
    if not f or not desde:
        return None
    rspe = [c.get("processo_criminal") or "" for c in r.get("_crimes", [])] + [r.get("processo_execucao") or ""]
    rspe = [x for x in rspe if rs.chave_processo(x)]
    ult = None
    for e in sorted(f.get("eventos", []), key=lambda e: _dp(e.get("data") or "") or date.min):
        x, t = _dp(e.get("data") or ""), e.get("texto") or ""
        if not x or x < desde:
            continue
        if _saida_fim_custodia(t) and not RE_PENA_EXTINTA_FICHA.search(t):
            break  # soltura: acabou a custódia que começou em 'desde'
        m = RE_PENA_EXTINTA_FICHA.search(t)
        if not m:
            continue
        d = _dp(m.group(1))
        autos = rs.processos_no_texto(t[m.end():])
        if d and d >= desde and autos and not any(rs.processo_parecido(a, q) for a in autos for q in rspe):
            ult = (d, autos[0])
    return ult


RE_ENTRADA_MONITORA = re.compile(r"ENTRADA NA UNIDADE PENAL:\s*UNIDADE MISTA DE MONITORA|ENTRADA NA UNIDADE PENAL:\s*[^,]*MONITORA[ÇC]|ENTRANDO NA MONITORA", re.I)
RE_SAIDA_MONITORA = re.compile(r"SAINDO DA UNIDADE DE MONITORA|SA[ÍI]DA DA UNIDADE PENAL:\s*UNIDADE MISTA DE MONITORA", re.I)


def _execucao_parada_ou_extinta(r):
    """Execução extinta, arquivada ou suspensa no SEEU (status do processo de execução ou todos os crimes extintos)."""
    _cr = r.get("_crimes", [])
    st = rs._sem_acento(r.get("status_execucao") or "").upper()
    return bool(r.get("execucao_extinta")) or bool(re.search(r"SUSPENS|SOBRESTAD|ARQUIVAD|EXTINT|BAIXAD", st)) or \
        (bool(_cr) and all((c.get("extinto") or "").upper().startswith("S") for c in _cr))


def reconciliar_eventos(r, f):
    """RSPE x ficha na retomada do cumprimento. Omissão: o último evento do RSPE é uma interrupção (que não é prisão em
    outro processo) e a ficha registra nova entrada no sistema prisional depois dela, sem saída em liberdade posterior -
    o reinício é lançado pela ficha (evento marcado _ficha), e os cálculos passam a considerar a custódia. Divergência:
    reinício no RSPE posterior à entrada vinda de fora registrada na ficha - devolve o aviso (não altera o RSPE).
    Altera r no lugar; devolve [(tipo, dados)] para a Auditoria."""
    r["_eventos"] = [e for e in r.get("_eventos", []) if not e.get("_ficha")]
    r.pop("_custodia_ficha", None); r.pop("_reconc_ficha", None); r.pop("_custodias_ficha_outro", None); r.pop("_custodia_ficha_proc", None)
    r.pop("_detracao_ficha", None)
    r["_tem_ficha"] = bool(f)
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
        _sol = max((x for x, t in ev if d < x < g1 and _saida_fim_custodia(t)), default=None)
        rua = [(x, t) for x, t in ev if d < x < g1 - timedelta(days=2) and RE_ENTRADA_RUA.search(t) and not (_sol and x <= _sol)]
        if rua:
            mm = re.search(r"PROCEDENTE:\s*([^,]+)", rua[0][1], re.I)
            avisos.append(("reinicio-divergente", {"interrupcao": d, "reinicio": g1, "entrada": rua[0][0], "origem": mm.group(1).strip() if mm else "",
                                                   "motivo": (e.get("motivo") or "").strip()}))
    # omissão: parado no RSPE, preso segundo a ficha
    if evs and "INTERRUP" in (evs[-1].get("tipo") or "").upper() and not rs.RE_OUTRO_PROC.search(evs[-1].get("motivo") or ""):
        d = rs.to_date(evs[-1]["data"])
        # entrada na unidade de monitoramento eletrônico (UMMVE) não é prisão; e a custódia atual é a que começa depois da última
        # saída (soltura, saída judicial, saída da monitoração) - uma monitoração cautelar já encerrada não é o reinício
        entradas = [(x, t) for x, t in ev if x > d and RE_ENTRADA.search(t) and not RE_ENTRADA_MONITORA.search(t)]
        _ult_saida = max((y for y, u in ev if y > d and (_saida_fim_custodia(u) or RE_SAIDA_MONITORA.search(u))), default=None)
        if _ult_saida and any(x >= _ult_saida for x, _t in entradas):
            entradas = [(x, t) for x, t in entradas if x >= _ult_saida]
        if entradas:
            x, t = entradas[0]
            ok, _ = custodia_apos(f, x - timedelta(days=1))
            # só é retomada se a pessoa esteve fora: entrada vinda da delegacia/audiência de custódia, ou saída em liberdade
            # entre a interrupção e a entrada. Transferência entre unidades = custódia contínua (provável prisão em outro
            # processo): não se lança nada - a Auditoria alerta a contradição
            fora = RE_ENTRADA_RUA.search(t) or _entrada_fim_fuga(t, ev, x, d) or any(d - timedelta(days=3) <= y < x and _saida_fim_custodia(u) for y, u in ev)
            _cls = custodia_ficha_processo(r, f, _dp(f.get("data_prisao") or "") if (_dp(f.get("data_prisao") or "") and d < _dp(f.get("data_prisao") or "") < x) else x)
            if ok and fora and _cls and (_cls["tipo"] == "civil" or (_cls["tipo"] == "outro" and _execucao_parada_ou_extinta(r))):
                # prisão civil, ou prisão por outro processo com a execução suspensa/extinta no SEEU: não é reinício desta pena
                avisos.append(("custodia-nao-desta", {"interrupcao": d, "entrada": x, "texto": _cls["texto"], "tipo": _cls["tipo"],
                                                      "motivo": (evs[-1].get("motivo") or "").strip()}))
                fora = False
            if ok and fora:
                mm = re.search(r"PROCEDENTE:\s*([^,]+)", t, re.I)
                rua = bool(RE_ENTRADA_RUA.search(t) or _entrada_fim_fuga(t, ev, x, d))
                # a "Data Prisão" da ficha, poucos dias antes da entrada na unidade (delegacia, audiência de custódia), é o início
                # da custódia: o reinício vai nela, para o confronto da prisão com a ficha não alertar contra o próprio lançamento
                _xp = _dp(f.get("data_prisao") or "")
                # ... salvo se entre ela e a entrada há saída em liberdade (alvará): aí a "Data Prisão" é da custódia anterior, e a nova
                # prisão é a entrada
                if _xp and d < _xp < x and (x - _xp).days <= 30 and not any(_xp <= y < x and _saida_fim_custodia(u) for y, u in ev):
                    x = _xp
                # item 51 de 16/10: depois de liberdade provisória, relaxamento ou regime aberto, a nova prisão pode ser por outro
                # processo (suspensão, não reinício) - reinício e suspensão levam a data-base e prescrição opostas: nada se lança
                # até se saber em que processo foi a prisão ("verificar")
                _cr = r.get("_crimes", [])
                if r.get("execucao_extinta") or (bool(_cr) and all((c.get("extinto") or "").upper().startswith("S") for c in _cr)) or \
                        re.search(r"LIBERDADE PROVIS|RELAXAMENTO|ABERTO", rs._sem_acento(evs[-1].get("motivo") or "").upper()):
                    # execução extinta: a nova prisão é de outro processo - não há reinício a lançar (o aviso diz isso)
                    avisos.append(("reinicio-a-conferir", {"interrupcao": d, "entrada": x, "origem": mm.group(1).strip() if mm else "", "rua": rua,
                                                           "motivo": (evs[-1].get("motivo") or "").strip()}))
                else:
                    _oe = extincao_outra_execucao(r, f, x)
                    if _oe:
                        avisos.append(("custodia-outra-execucao", {"entrada": x, "extincao": _oe[0], "autos": _oe[1]}))
                        x = _oe[0] + timedelta(days=1)
                    r["_eventos"].append({"tipo": "REINÍCIO", "motivo": "%s (lançado pela ficha SIAPEN)" % ("RECAPTURA" if rua else "ENTRADA NO SISTEMA PRISIONAL"),
                                          "complemento": "", "data": rs.fmt(x), "data_decisao": "", "data_referencia": "", "processos": "", "_ficha": True})
                    r["_eventos"].sort(key=lambda e2: rs.to_date(e2.get("data") or "") or date.min)
                    avisos.append(("reinicio-pela-ficha", {"interrupcao": d, "entrada": x, "origem": mm.group(1).strip() if mm else "", "rua": rua,
                                                           "motivo": (evs[-1].get("motivo") or "").strip()}))
    # omissão: nenhum evento de prisão no RSPE, e a ficha registra a entrada no sistema prisional
    if not evs:
        ent = [(x, t) for x, t in ev if RE_ENTRADA.search(t)]
        x0 = _dp(f.get("data_prisao") or "") or (ent[0][0] if ent else None)
        _cls = custodia_ficha_processo(r, f, x0) if x0 else None
        if x0 and _cls and (_cls["tipo"] == "civil" or (_cls["tipo"] == "outro" and _execucao_parada_ou_extinta(r))):
            # prisão civil, ou prisão por outro processo com a execução suspensa no SEEU: não é o início desta pena
            avisos.append(("custodia-nao-desta", {"interrupcao": None, "entrada": x0, "texto": _cls["texto"], "tipo": _cls["tipo"], "motivo": ""}))
            x0 = None
        _oe = extincao_outra_execucao(r, f, x0) if x0 else None
        if _oe:
            # a custódia serviu a outra execução até a extinção dela: esta só começa no dia seguinte
            avisos.append(("custodia-outra-execucao", {"entrada": x0, "extincao": _oe[0], "autos": _oe[1]}))
            x0 = _oe[0] + timedelta(days=1)
        if x0:
            r["_eventos"].append({"tipo": "PRISÃO", "motivo": "ENTRADA NO SISTEMA PRISIONAL (lançada pela ficha SIAPEN)", "complemento": "",
                                  "data": rs.fmt(x0), "data_decisao": "", "data_referencia": "", "processos": "", "_ficha": True})
            avisos.append(("inicio-pela-ficha", {"entrada": x0}))
    # custódia atual segundo a ficha (depois do último evento do RSPE): afasta o "não iniciou o cumprimento" quando a
    # única prisão registrada é a provisória
    evs2 = sorted((e for e in r["_eventos"] if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    r["_custodia_ficha"] = custodia_apos(f, rs.to_date(evs2[-1]["data"]))[0] if evs2 else None
    # custódia em curso sem processo indicado no RSPE (ou lançada pela ficha): a que processo a ficha a vincula
    r.pop("_custodia_ficha_proc", None)
    _ab = [(a, p) for a, b, _m, p in rs.periodos_custodia_detalhe(r["_eventos"]) if b is None]
    if _ab and not rs.lista_processos(_ab[-1][1]):
        _cl = custodia_ficha_processo(r, f, _ab[-1][0])
        if _cl:
            r["_custodia_ficha_proc"] = dict(_cl, desde=rs.fmt(_ab[-1][0]))
    r["_reconc_ficha"] = avisos
    r["_custodias_ficha_outro"] = [(rs.fmt(a), rs.fmt(b), ps) for a, b, ps in custodias_outro_processo(r, f)]
    # prisão provisória encerrada, pelo próprio processo, que o RSPE trata como liberdade: detração obrigatória (CP, art. 42) - entra
    # no término que o programa calcula para a guia sem cálculo (rspe_view.custodia_sem_calculo)
    try:
        r["_detracao_ficha"] = [(rs.fmt(d["ini"]), rs.fmt(d["fim"]), d["processo"]) for d in detracoes_ficha(r, f)]
    except Exception:
        r["_detracao_ficha"] = []
    return avisos


def _sem_fuga_falsa(t):
    """Texto sem o que parece fuga ou soltura e não é: tentativa de fuga, ameaça ("sob pena de evasão imediata"), não retorno do
    hospital/plantão (internação) e saída por alvará de transferência (mudança de regime, sem liberdade)."""
    u = rs._sem_acento(t or "").upper()
    u = re.sub(r"TEN\w*TATIVA\s+(?:DE\s+)?(?:FUGA|EVASAO)|SOB PENA DE (?:EVASAO|FUGA)|MOTIVO:\s*ALVARA DE TRANSFERENCIA", " ", u)
    if re.search(r"HOSPITAL|INTERNAC|INTERNAD|PLANTAO|CONSULTA", u) and not re.search(r"EVADI|\bFUGA\b|EVASAO|FORAGID", u):
        u = u.replace("NAO RETORNOU", " ")
    _LIB = r"ALVARA|SOLTURA|LIBERDADE|\bFUGA\b|FUGIR|EVADI\w*|EVASAO|FORAGID\w*|NAO RETORNOU"
    # mudança de cela, entrada, recaptura e reapresentação só citam a fuga ou o alvará ("Motivo: AGUARDANDO CONSULTA DE ALVARÁ",
    # "ENTRADA NO EPJFC ... MOTIVO: EVASÃO DO EPRACA", "FOI PRESO POR EVASÃO", "RETORNOU DE EVASÃO"): não são saída
    if re.match(r"MUDANCA DE CELA", u) or re.search(r"ENTRADA NA UNIDADE|DEU ENTRADA|^\W*ENTRADA N[OA]\s|\b(?:RE)?INGRESSOU|RECAPTURA|REAPRESENTA|APRESENTA\w*(?:-SE)? ESPONTANE|"
                                                  r"APRESENTOU-?SE ESPONTANE|RETORN\w* D[AE] (?:EVASAO|FUGA)|\bPRES[OA] (?:POR|EM RAZAO D[AE]|PELA?) (?:EVASAO|FUGA)", u):
        u = re.sub(_LIB, " ", u)
    # alvará citado sem soltura ("tomou ciência do Alvará ... Não foi colocado em liberdade devido pendência"; parecer da Central de
    # Alvarás) e fuga só narrada (termo de assentada, reconhecimento da falta, ciência de regressão, aviso "será considerado evasão",
    # "para fugir, mas não teve coragem")
    if re.search(r"NAO FOI (?:COLOCAD|POST)\w* EM LIBERDADE|CENTRAL DE ALVARA|PARECER DA CA\b|TERMO DE ASSENTADA|RECONHECO A PRATICA|"
                 r"^\W*REGRESSAO DE REGIME|SERA CONSIDERAD[OA] (?:COMO )?(?:EVASAO|FUGA)|NAO TEVE CORAGEM|SE INCORRER", u):
        u = re.sub(_LIB, " ", u)
    # saída por determinação judicial com destino em unidade prisional (transferência, não liberdade)
    m = re.search(r"SAIDA DA UNIDADE PENAL:.*?DESTINO:\s*([^,]+),\s*MOTIVO:\s*DETERMINACAO JUDICIAL", u)
    if m and (classificar_unidade(m.group(1))[0] in ("fechado", "semiaberto", "provisorio", "federal") or
              re.search(r"\b(?:PDIB|IPCG|EPJFC|PTRAN|CPAIG|PED|EPMR|EPA|PEMRFG\w*|PHAC|UPRB)\b|UNIDADE PENAL|PENITENC|PRESIDIO|ESTAB\w*\.? PENAL", m.group(1))):
        u = re.sub(r"DETERMINACAO JUDICIAL", "TRANSFERENCIA", u)
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
    (r"AGROINDUSTRIAL|\bCPAIG\b", "semiaberto", "Centro Penal Agroindustrial da Gameleira (semiaberto masculino)"),
    # siglas das fichas antigas ("ENTRADA NO EPMRSAAC", "DEU ENTRADA NO PJFC"): regime semiaberto/aberto e unidades de regime fechado
    (r"^\s*(?:EP\w*RSA\w*|UPRSA\w*|CPAG)\s*$", "semiaberto", "Estabelecimento de regime semiaberto (sigla)"),
    (r"^\s*(?:PJFC|PHAC|PDIB|EPMC|EPC|EPA|UPRB|EPRB|PSM\w*|EPMR)\s*$", "fechado", "Estabelecimento de regime fechado (sigla)"),
    (r"SEMI[- ]?ABERTO", "semiaberto", "Estabelecimento de regime semiaberto (e aberto/albergado)"),
    (r"COL[ÔO]NIA PENAL", "semiaberto", "Colônia Penal (semiaberto)"),
    (r"ALBERGAD|\bEPRACAG?\b", "aberto", "Casa do Albergado / assistência ao albergado (regime aberto)"),
    (r"AUDI[ÊE]NCIA DE CUST[ÓO]DIA|\bCPAC\b", "provisorio", "Central Provisória de Audiência de Custódia (CPAC)"),
    (r"TRIAGEM|^\s*CT\s*$", "provisorio", "Centro de Triagem (Anísio Lima / feminino Irmã Irma Zorzi)"),
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


def unidade_incerta(nome):
    """Unidade classificada como de regime fechado só pelo nome genérico (estabelecimento penal, presídio, cadeia, sigla de
    estabelecimento penal) ou com ala/anexo: pode abrigar o semiaberto. A penitenciária é de regime fechado (LEP, art. 87)."""
    reg, rot = classificar_unidade(nome)
    u = rs._sem_acento(nome or "").upper()
    if re.search(r"\bALA\b|ANEXO", u):
        return True
    if rot == "Estabelecimento de regime fechado":
        return "PENITENCI" not in u
    if rot == "Estabelecimento de regime fechado (sigla)":
        return not re.match(r"\s*P", u)
    return False


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


def penas_extintas_no_periodo(r, a, b):
    """Crimes desta execução extintos (cumprimento, indulto...) com data de extinção entre a e b (até 1 dia depois de b): a
    custódia que a ficha mostra nesse intervalo, fora do cômputo das penas em curso, pode ter sido o cumprimento dessas penas
    (livramento revogado, pena antiga retomada até a extinção) - o tempo já usado numa pena não se detrai de novo. Devolve o
    texto curto ("art. 157 ... e art. 121 ..., extintas em 07/06/2022") ou ""."""
    if not a or not b:
        return ""
    ext = [c for c in r.get("_crimes", []) if (c.get("extinto") or "").upper().startswith("S")
           and (d := rs.to_date(c.get("data_extincao") or "")) and a <= d <= b + timedelta(days=1)]
    if not ext:
        return ""
    datas = sorted({c["data_extincao"] for c in ext}, key=rs.to_date)
    return "%s, %s em %s" % (rs.crimes_curto([dict(c, extinto="") for c in ext]), "extinta" if len(ext) == 1 else "extintas", ", ".join(datas))


# prisão civil (dívida de alimentos): não é custódia penal - não é cumprimento de pena nem detração (CP, art. 42)
RE_PRISAO_CIVIL = re.compile(r"PENS[AÃ]O ALIMENT|ALIMENT[IÍ]CI|\bALIMENTOS\b|PRIS[AÃ]O CIVIL|DEVEDOR DE ALIM", re.I)


def _arts_cabecalho(txt):
    """Artigos citados no campo "Artigo" do cabeçalho da ficha ("ART.121, 157 "CAPUT" C/C 61", "33 DA LEI 11.343/06 / 157-CPB")."""
    t = rs._sem_acento(txt or "").upper()
    t = re.sub(r"\bLEI\s*(?:N[º°O.]*\s*)?[\d.]+(?:/\d{2,4})?|\d{1,2}\.\d{3}(?:/\d{2,4})?", " ", t)  # o número da lei não é artigo
    t = re.sub(r"(?:§|\bPAR(?:AGRAFO)?\b\.?|\bINC(?:ISO)?\b\.?)\s*[\dIVXº°]+", " ", t)  # parágrafo e inciso
    t = re.sub(r"\b(?:C/C|CC)\s*(?:ART\.?\s*)?\d+(?:-[A-Z])?(?:\s*,\s*\d+)*", " ", t)  # concurso/agravante (art. 61, 69, 70, 71)
    return {m.group(1) + (("-" + m.group(2)) if m.group(2) else "") for m in re.finditer(r"(?<![\d/])(\d{1,3})(?:\s*-?\s*([A-Z])\b)?(?![\d/])", t)}


def custodia_ficha_processo(r, f, desde):
    """A que se refere, pela ficha, a custódia que começa em 'desde' (prisão sem processo indicado no RSPE, ou lançada pela ficha):
    'civil' (prisão por pensão alimentícia - não é pena), 'desta' (a ficha cita processo do RSPE), 'outro' (a ficha cita só
    autos que o RSPE não lista, ou o cabeçalho registra "PROCESSADO" por artigos que não são os desta execução) ou None (a ficha
    não diz). Devolve {"tipo", "autos", "artigo", "texto"} (texto curto para a tela) ou None."""
    if not f or not desde:
        return None
    rspe = [c.get("processo_criminal") or "" for c in r.get("_crimes", [])] + [r.get("processo_execucao") or ""]
    rspe += [p for e in r.get("_eventos", []) + r.get("_incidentes", []) if not e.get("_ficha") for p in rs.lista_processos(e.get("processos") or "")]
    rspe = [x for x in rspe if rs.chave_processo(x)]
    ev = sorted(((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])), key=lambda x: x[0] or date.min)
    autos, saida = [], None
    for x, t in ev:
        if not x or x < desde - timedelta(days=10):
            continue
        _fim = _saida_fim_custodia(t) and x > desde
        # os autos citados na própria saída (ofício, alvará, progressão) também são da custódia que ela encerra
        for n in rs.processos_no_texto(t):
            if n not in autos:
                autos.append(n)
        if _fim:
            saida = (x, _br(t)[:160])
            break  # soltura depois do início: o que vem depois é outra custódia
    if saida is None:
        # saída da unidade para fora do sistema (progressão na comarca de origem, por exemplo) seguida de nova entrada vinda da rua:
        # a custódia não foi contínua
        for k, (x, t) in enumerate(ev):
            if x and x > desde and re.search(r"SA[ÍI]DA DA UNIDADE PENAL", t, re.I):
                _prox = next(((x2, t2) for x2, t2 in ev[k + 1:] if x2 and RE_ENTRADA.search(t2)), None)
                if _prox and RE_ENTRADA_RUA.search(_prox[1]) and (_prox[0] - x).days > 2:
                    saida = (x, _br(t)[:160])
                    break
    desta = [n for n in autos if any(rs.processo_parecido(n, q) for q in rspe)]
    outros = [n for n in autos if n not in desta]
    # cabeçalho: vale para a prisão atual (Data Prisão até 30 dias antes do início ou depois dele)
    dp = _dp(f.get("data_prisao") or "")
    cab = bool(dp and dp >= desde - timedelta(days=30))
    art = (f.get("artigo") or "").strip() if cab else ""
    cond = (f.get("condenacao") or "").strip() if cab else ""
    if art and RE_PRISAO_CIVIL.search(art):
        return {"tipo": "civil", "autos": outros, "artigo": art,
                "texto": "a ficha registra prisão civil (Artigo: %s), que não é cumprimento de pena nem detração" % art.lower()}
    if desta:
        return {"tipo": "desta", "autos": desta, "artigo": art, "texto": "a ficha vincula a custódia aos autos %s, desta execução" % ", ".join(desta),
                "saida": (rs.fmt(saida[0]), saida[1]) if saida else None}
    arts_r = {rs.num_art(c.get("artigo") or "") for c in r.get("_crimes", []) if not (c.get("extinto") or "").upper().startswith("S")}
    arts_f = _arts_cabecalho(art)
    art_outro = bool(cond.upper().startswith("PROCESSAD") and arts_f and arts_r and not (arts_f & arts_r))
    if outros or art_outro:
        partes = []
        if outros:
            partes.append("autos %s, que o RSPE não lista" % ", ".join(outros))
        if art_outro:
            partes.append("cabeçalho \"PROCESSADO\", Artigo: \"%s\", crime que não é desta execução" % art.rstrip(" ,;"))
        return {"tipo": "outro", "autos": outros, "artigo": art,
                "texto": "a ficha vincula a custódia a outro processo (%s)" % "; ".join(partes)}
    return None


def custodias_outro_processo(r, f):
    """Prisões encerradas que só a ficha mostra (entrada vinda da rua até a soltura ou a saída para o monitoramento), vinculadas pela
    ficha só a autos que o RSPE não lista e fora da custódia do RSPE: [(inicio, fim, [autos])]. Servem à detração em processo
    diverso (fato desta execução anterior à prisão - CP, art. 42), a conferir."""
    if not f:
        return []
    rspe = [c.get("processo_criminal") or "" for c in r.get("_crimes", [])] + [r.get("processo_execucao") or ""]
    rspe += [o.get("processo_criminal") or "" for o in r.get("_outras_condenacoes") or []]
    rspe = [x for x in rspe if rs.chave_processo(x)]
    per = rs.periodos_custodia([e for e in r.get("_eventos", []) if not e.get("_ficha")])
    ev = sorted(((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])), key=lambda x: x[0] or date.min)
    out, ini, autos = [], None, []
    for x, t in ev:
        if not x:
            continue
        if ini is None:
            if RE_ENTRADA_RUA.search(t):
                ini, autos = x, list(rs.processos_no_texto(t))
            continue
        fim = _saida_fim_custodia(t) or re.search(r"SA[ÍI]DA DA UNIDADE PENAL.*DESTINO:\s*UNIDADE MISTA DE MONITORA|MONITORA[ÇC][ÃA]O ELETR", t, re.I)
        autos += [n for n in rs.processos_no_texto(t) if n not in autos]
        if fim:
            if autos and not any(rs.processo_parecido(n, q) for n in autos for q in rspe) and \
                    not any(a <= x and (b is None or b >= ini) for a, b in per):
                out.append((ini, x, autos))
            ini, autos = None, []
    return out


def nascimento_muda_marco(r, d1, d2):
    """A diferença entre as duas datas de nascimento muda algum marco de idade: 18/21 anos no fato, 70 na sentença (CP, arts. 27 e
    115), 60/70 nos decretos e hoje."""
    _id = lambda n, ref: ref.year - n.year - ((ref.month, ref.day) < (n.month, n.day))
    _refs = [(rs.to_date(c.get("data_infracao") or ""), (18, 21)) for c in r.get("_crimes", [])]
    _refs += [(rs.to_date(c.get("data_sentenca") or ""), (70,)) for c in r.get("_crimes", [])]
    _refs += [(x, (60, 70)) for x in list(rs.DECRETOS.values()) + [date(2022, 12, 25), date.today()]]
    return any(ref and any((_id(d1, ref) >= k) != (_id(d2, ref) >= k) for k in ks) for ref, ks in _refs)


def _identidade_x_ficha(r, f):
    """Mesma pessoa? CPF, nome e nascimento da ficha x RSPE (a ficha vinculada pode ser de homônimo ou o cadastro estar errado)."""
    out = []
    c1, c2 = re.sub(r"\D", "", r.get("cpf") or ""), re.sub(r"\D", "", f.get("cpf") or "")
    if len(c1) == 11 and len(c2) == 11 and c1 != c2:
        _dif = sum(1 for a, b in zip(c1, c2) if a != b)
        _dig = (" Os números diferem só em dígitos trocados, deslocados ou em até dois dígitos: provável erro de digitação em um dos cadastros."
                if _dif <= 2 or sorted(c1) == sorted(c2) or c1[1:] == c2[:-1] or c1[:-1] == c2[1:] else "")
        out.append(_item_rf("alerta", "CPF da ficha (%s) difere do RSPE (%s)" % (f.get("cpf"), r.get("cpf")),
                            "A ficha vinculada pode ser de outra pessoa (homônimo) ou um dos cadastros está errado. Conferir antes de usar os dados da ficha." + _dig,
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
        muda = nascimento_muda_marco(r, d1, d2)
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
    if any(x < y < s and (_saida_fim_custodia(t) or re.search(r"SALVO[- ]CONDUTO|TRANSFER[ÊE]NCIA PARA (O )?ESTADO", t, re.I))
           for y, t in ((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])) if y):
        # a ficha registra soltura (ou saída para outro estado, com salvo-conduto) no intervalo: não é custódia contínua até o
        # início no RSPE
        return []
    # o início pode ser o reinício que o programa lançou a partir da ficha (evento _ficha), não um registro do RSPE
    pela_ficha = any(e.get("_ficha") and rs.to_date(e.get("data") or "") == s for e in evs)
    if any(a <= x <= b for a, b in _soltura_x_ficha(r, f, so_periodos=True)):
        return []  # dentro da interrupção sem soltura na ficha: o item dela já conta esses dias
    _oe = extincao_outra_execucao(r, f, x)
    if _oe and _oe[0] + timedelta(days=1) >= s:
        return []  # a custódia serviu a outra execução até a extinção dela (item próprio "serviu a outra execução")
    _ext = penas_extintas_no_periodo(r, x, s)
    if _ext:
        return [_item_rf("verificar", "Custódia na ficha desde %s, antes do início no RSPE (%s): pode ter servido às penas extintas" % (
                             rs.fmt(x), rs.fmt(s)),
                         "A ficha registra a prisão em %s, e o RSPE só conta o cumprimento a partir de %s. Nesse intervalo terminaram penas "
                         "desta execução (%s): a custódia provavelmente foi o cumprimento delas, e o tempo já usado numa pena não se "
                         "detrai de novo. Conferir na decisão de extinção a que pena o período foi imputado; se sobrar tempo depois da "
                         "extinção, ele é detração da pena atual." % (rs.fmt(x), rs.fmt(s), _ext),
                         "CP, art. 42; LEP, art. 111.")]
    return [_item_rf("alerta", ("Prisão em %s na ficha; cômputo só a partir de %s, reinício lançado pela ficha (%s sem cômputo)" if pela_ficha else
                                "Prisão em %s na ficha; RSPE só registra início em %s (%s sem cômputo)") % (rs.fmt(x), rs.fmt(s), rs.pl((s - x).days, "dia", "dias")),
                     "A ficha registra a prisão em %s; %s trata o período até %s como liberdade. Se a prisão foi por este processo (ou por processo "
                     "unificado), os dias entram como detração e antecipam progressão, livramento e término. Conferir o auto de prisão e pedir a retificação." % (
                         rs.fmt(x), "o cálculo (RSPE com o reinício lançado pelo programa a partir da ficha)" if pela_ficha else "o RSPE", rs.fmt(s)),
                     "CP, art. 42; LEP, art. 111.")]


RE_PENDENCIA_ALVARA = re.compile(r"PEND[ÊE]NCIA|(?<!N[ÃA]O )(?:EXISTEM?|H[ÁA]) IMPEDIMENTO", re.I)


def _soltura_x_ficha(r, f, so_periodos=False):
    """Interrupção do RSPE por liberdade provisória (ou relaxamento) em que a ficha registra, na mesma data, o alvará com pendência
    (impedimento para a soltura) e nenhuma saída em liberdade até o reinício seguinte do RSPE: a pessoa não foi solta - a liberdade
    provisória foi de outro processo (flagrante novo) ou não se efetivou, e o tempo seguiu como custódia ou cumprimento em regime.
    Os dias entre a interrupção e o reinício (ou a primeira saída em liberdade) ficam fora da conta."""
    evs = [e for e in r.get("_eventos", []) if not e.get("_ficha") and rs.to_date(e.get("data") or "")]
    ev = sorted(((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])), key=lambda x: x[0] or date.min)
    ev = [(x, t) for x, t in ev if x]
    meus = [c.get("processo_criminal") or "" for c in r.get("_crimes", [])] + [r.get("processo_execucao") or ""]
    out = []
    for k, e in enumerate(evs):
        if "INTERRUP" not in (e.get("tipo") or "").upper() or not re.search(r"LIBERDADE PROVIS|RELAXAMENTO", rs._sem_acento(e.get("motivo") or "").upper()):
            continue
        d = rs.to_date(e["data"])
        pend = [t for x, t in ev if abs((x - d).days) <= 1 and RE_PENDENCIA_ALVARA.search(t)]
        if not pend:
            continue
        prox = next((rs.to_date(x["data"]) for x in evs[k + 1:] if "INTERRUP" not in (x.get("tipo") or "").upper()), None)
        lim = prox or date.today()
        # primeira saída em liberdade (alvará, fuga, evasão) depois da interrupção; a ida ao semiaberto, ao monitoramento ou ao aberto
        # por progressão é cumprimento, não soltura
        livre = next((x for x, t in ev if d <= x <= lim and RE_SAIDA_LIVRE.search(t) and not RE_PENDENCIA_ALVARA.search(t)), None)
        fim = min(lim, livre) if livre else lim
        dias = (fim - d).days - 1
        if dias < 2:
            continue
        desta = any(rs.processo_parecido(n, q) for t in pend for n in rs.processos_no_texto(t) for q in meus if rs.chave_processo(q))
        if so_periodos:
            out.append((d, fim))
            continue
        out.append(_item_rf("alerta" if desta else "verificar",
                            "Interrupção de %s (liberdade provisória) sem soltura na ficha: %s fora da conta até %s" % (
                                rs.fmt(d), rs.pl(dias, "dia", "dias"), rs.fmt(fim)),
                            "O RSPE interrompe o cumprimento em %s por %s, mas a ficha registra na mesma data o alvará com pendência (%s) e "
                            "nenhuma saída em liberdade até %s. A pessoa continuou presa (ou cumprindo a pena no regime): a liberdade provisória "
                            "pode ter sido de outro processo. Esses dias são pena cumprida (CP, art. 42; LEP, art. 111): conferir e pedir a "
                            "retificação do RSPE%s." % (
                                rs.fmt(d), (e.get("motivo") or "").strip().lower(), _br(pend[0])[:160], rs.fmt(fim),
                                " (a pendência cita esta execução)" if desta else ""),
                            "CP, art. 42; LEP, arts. 111 e 112."))
    return out


def detracoes_ficha(r, f, so_periodos=False):
    """Prisões encerradas na ficha (entrada vinda da rua até a soltura por alvará) por processo que integra o RSPE, em período que o
    RSPE trata como liberdade: [{"ini" (a partir do fato), "fim", "preso_desde", "fato", "dias" (fora dos períodos do RSPE),
    "processo", "crime"}]. Base do item de detração da Auditoria e do término calculado da guia sem cálculo (rspe_view).
    so_periodos: modo das estimativas (aceita RSPE sem eventos e número de alvará truncado)."""
    evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
    if not f or (not evs and not so_periodos):
        return []
    per = rs.periodos_custodia(evs)
    crimes = {}
    for c in r.get("_crimes", []):
        k = rs.chave_processo(c.get("processo_criminal") or "")
        if k:
            crimes.setdefault(k, c)
    ev = sorted(((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])), key=lambda x: x[0] or date.min)
    ev = [(x, t) for x, t in ev if x]
    dp = _dp(f.get("data_prisao") or "")
    out, ini, ult_saida = [], None, None
    for x, t in ev:
        if ini is None and RE_ENTRADA_RUA.search(t):
            ini = x
            # a prisão (na delegacia) costuma ser dias antes da entrada na unidade: a data de prisão da ficha, se cai entre a soltura
            # anterior e a entrada, é o início
            if dp and dp <= x and (x - dp).days <= 30 and (ult_saida is None or dp > ult_saida):
                ini = dp
        elif ini is not None and re.search(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(ALVAR|SOLTURA|LIBERDADE)", t, re.I):
            _ma = re.search(r"ALVAR[ÁA][^:]*:\s*(.*)", t, re.I)
            _na = rs.processos_no_texto(_ma.group(1))[:1] if _ma else []  # também grafado sem pontos ("AUTOS0801005...", "Nº.09000036-...")
            if not _na and _ma and so_periodos:
                # número truncado no alvará ("0900066-29.2025.8.12.001"): o número, o dígito e o ano bastam para achar o processo
                _mt = re.search(r"(\d{7})-?(\d{2})\.?(\d{4})", _ma.group(1))
                _na = [k.zfill(20) for k in crimes if _mt and k.zfill(20)[:13] == "".join(_mt.groups())][:1]
            m = re.match(r"(.*)", _na[0]) if _na else None
            c = crimes.get(rs.chave_processo(m.group(1))) if m else None
            if m and not c:
                # número do alvará com erro de digitação (um dígito trocado, dígitos invertidos): o mesmo processo do RSPE
                c = next((v for k, v in crimes.items() if rs.processo_parecido(m.group(1), k.zfill(20))), None)
            if c:
                fora = [ini + timedelta(days=i) for i in range((x - ini).days + 1)]
                fato = rs.to_date(c.get("data_infracao") or "")
                # só conta a partir do fato do crime desse processo (antes dele, a prisão era por outro motivo - CP, art. 42)
                fora = [d for d in fora if not any(a <= d and (b is None or d <= b) for a, b in per) and (not fato or d >= fato)]
                if len(fora) >= 2:
                    out.append({"ini": max(ini, fato) if fato else ini, "fim": x, "preso_desde": ini, "fato": fato, "dias": len(fora),
                                # o número do RSPE (o da ficha pode ter erro de digitação)
                                "processo": c.get("processo_criminal") or m.group(1), "crime": c})
            ini, ult_saida = None, x
        elif ini is not None and _saida_fim_custodia(t):
            ini, ult_saida = None, x  # fuga, evasão, livramento: fim da custódia sem detração a apurar aqui
    return out


def _detracao_x_ficha(r, f, so_periodos=False):
    """Prisão encerrada na ficha por processo que integra o RSPE, em período que o RSPE trata como liberdade (detracoes_ficha): os
    dias faltam como detração (CP, art. 42). A prisão em curso fica com _prisao_x_ficha."""
    if so_periodos:
        return [(d["ini"], d["fim"], d["dias"]) for d in detracoes_ficha(r, f, True)]
    out = []
    for d in detracoes_ficha(r, f):
        i0, x, ini, fato, _pn, c, n = d["ini"], d["fim"], d["preso_desde"], d["fato"], d["processo"], d["crime"], d["dias"]
        out.append(_item_rf("alerta", "Detração: prisão de %s a %s na ficha (processo %s, deste RSPE) sem cômputo no RSPE - %s" % (
            rs.fmt(i0), rs.fmt(x), _pn, rs.pl(n, "dia", "dias")),
            ("Preso desde %s; conta a partir do fato (%s). " % (rs.fmt(ini), rs.fmt(fato)) if i0 != ini else "") +
            "A ficha registra a prisão de %s a %s, encerrada por alvará de soltura no processo %s (%s, fato em %s), que integra esta "
            "execução. O RSPE trata %s desse período como liberdade. A prisão provisória pelo próprio processo da condenação é "
            "detração obrigatória: os dias entram como pena cumprida e antecipam progressão, livramento, indulto e término. "
            "Conferir o auto de prisão e o alvará e pedir o lançamento da detração." % (
                rs.fmt(i0), rs.fmt(x), _pn, rs.crimes_curto([dict(c, extinto="")]), c.get("data_infracao") or "?",
                rs.pl(n, "dia", "dias")),
            "CP, art. 42; LEP, arts. 66, III, c, e 111."))
    return out


def solturas_nao_lancadas(r, f, judicial=False):
    """Saídas por alvará/soltura da ficha dentro de um período que o RSPE trata como prisão contínua (sem interrupção): o RSPE conta o
    tempo em liberdade como custódia - erro favorável ao assistido. Devolve [(soltura, nova entrada | None)]. judicial: também a saída
    por determinação judicial sem destino prisional nem nova entrada em até 3 dias (saida_judicial "a_conferir"), para estimativas
    que ficam a conferir."""
    if not f:
        return []
    evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "") and not e.get("_ficha")), key=lambda e: rs.to_date(e["data"]))
    per = rs.periodos_custodia(evs)
    ev = sorted(((_dp(e.get("data") or ""), e.get("texto") or "") for e in f.get("eventos", [])), key=lambda x: x[0] or date.min)
    ev = [(x, t) for x, t in ev if x]
    out = []
    for k, (x, t) in enumerate(ev):
        if not (re.search(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(ALVAR|SOLTURA|LIBERDADE)", t, re.I) and not re.search(r"TRANSFER", t, re.I)) \
                and not (judicial and (saida_judicial(t, ev, x) or ("",))[0] == "a_conferir"):
            continue
        if not any(a < x and (b is None or x < b - timedelta(days=1)) for a, b in per):
            continue
        y = next((x2 for x2, t2 in ev[k + 1:] if RE_ENTRADA_RUA.search(t2)), None)
        if y and (y - x).days <= 2:
            continue  # saída e volta no mesmo episódio (sem liberdade efetiva)
        out.append((x, y))
    return out


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
    fora = [p for p in rs.processos_no_texto(" ".join(f.get("autos") or [])) if rs.chave_processo(p) not in rspe]
    # número que difere de um processo do RSPE só por erro de digitação (um dígito, dígitos invertidos, um zero a mais, ou só o dígito
    # verificador): é o mesmo processo, não processo novo
    _sem_dv = lambda p: (lambda d: d[:7] + d[9:] if len(d) == 20 else d)(re.sub(r"\D", "", p or "").zfill(20))
    # ... ou só pelo segmento do tribunal (J.TR: "8.23" no lugar de "8.12"), com número, dígito verificador, ano e origem iguais
    # (só quando o número da ficha tem dígito verificador inválido: com o segmento trocado, o DV deixa de conferir - CNJ, Res. 65/2008)
    _sem_jtr = lambda p: (lambda d: d[:13] + d[16:] if len(d) == 20 else d)(re.sub(r"\D", "", p or "").zfill(20))
    _dv_ok = lambda p: (lambda d: len(d) == 20 and 98 - int(d[:7] + d[9:] + "00") % 97 == int(d[7:9]))(re.sub(r"\D", "", p or "").zfill(20))
    _rspe_n = [x for x in rspe if x]
    tipo = {p: next((q for q in _rspe_n if rs.processo_parecido(p, q) or _sem_dv(p) == _sem_dv(q)
                     or (_sem_jtr(p) == _sem_jtr(q) and not _dv_ok(p) and _dv_ok(q))), None)
            for p in fora}
    fora_real = [p for p in fora if not tipo[p]]
    _dig = [p for p in fora if tipo[p]]
    _dig_txt = " ".join("%s na ficha é provável erro de digitação de %s (difere só por um dígito, dígitos invertidos, o dígito verificador ou o segmento do tribunal)."
                        % (p, _cnj_fmt(tipo[p])) for p in _dig)
    if fora_real:
        return [_item_rf("info", "Processos na ficha que o RSPE não lista: %d" % len(fora_real),
                         "%s. Podem ser ações penais com condenação ainda não somada a esta execução (guia pendente - LEP, art. 111), prisões por outro "
                         "processo (suspensão) ou inquéritos/preventivas já encerrados. Conferir no SEEU e nos sistemas do TJ se há pena a unificar ou prisão "
                         "que deva ser computada.%s" % ("; ".join(fora_real), (" " + _dig_txt) if _dig_txt else ""), "LEP, art. 111; CP, art. 42.")]
    if _dig:
        return [_item_rf("info", "Número de processo na ficha com provável erro de digitação: %s" % "; ".join(_dig),
                         _dig_txt + " Tratado como o mesmo processo.", "LEP, art. 111.")]
    return []


def _cnj_fmt(chave):
    """Chave de processo (só dígitos) de volta ao formato CNJ, quando tem 20 dígitos com os zeros à esquerda."""
    d = (chave or "").zfill(20)
    return "%s-%s.%s.%s.%s.%s" % (d[:7], d[7:9], d[9:13], d[13], d[14:16], d[16:]) if len(d) == 20 else chave


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
    if tipo_un in ("fechado", "provisorio", "federal"):
        try:
            _lc, _dl = rs.livramento_em_curso(r, r.get("_incidentes", []))
        except Exception:
            _lc, _dl = False, None
        if _lc:
            # em livramento condicional, a pessoa presa em unidade fechada não indica falta de vaga (SV 56): indica nova prisão,
            # suspensão cautelar (LEP, art. 145) ou revogação do livramento (CP, arts. 86 e 87) não lançada no SEEU
            return [_item_rf("verificar", "Em livramento condicional no RSPE, mas a ficha registra a pessoa em unidade de regime %s (%s)" % (
                                 "fechado" if tipo_un != "provisorio" else "provisório", un.title()),
                             "Unidade atual%s: %s - %s. Provável nova prisão, suspensão do livramento ou revogação ainda não lançada no SEEU "
                             "(não é caso de falta de vaga). Conferir o motivo da prisão e a decisão sobre o livramento: a suspensão e a "
                             "revogação mudam o período de prova, a data-base e os demais benefícios." % (desde, un.title(), rot),
                             "LEP, arts. 140 e 145; CP, arts. 86, 87 e 88.")]
    if (reg.startswith("SEMI") or reg.startswith("ABERTO")) and tipo_un in ("fechado", "provisorio", "federal"):
        evs = sorted((e for e in r.get("_eventos", []) if rs.to_date(e.get("data") or "")), key=lambda e: rs.to_date(e["data"]))
        if "SUSPENSA" in (r.get("situacao_eventos") or r.get("situacao_cumprimento") or "").upper() or (
                evs and "INTERRUP" in (evs[-1].get("tipo") or "").upper() and rs.RE_OUTRO_PROC.search(evs[-1].get("motivo") or "")):
            return []  # execução suspensa (preso em outro processo): a unidade é a da outra prisão
        if any(tp == "custodia-nao-desta" for tp, _x in r.get("_reconc_ficha") or []):
            return []  # a ficha vincula a prisão atual a outro processo (ou é prisão civil): a unidade é a dessa prisão (item próprio)
        # nova prisão lançada pelo programa a partir da ficha (recaptura/reinício): justifica o fechado ou a regressão cautelar
        nova = [e for e in evs if e.get("_ficha")]
        # nova prisão na ficha ainda sem reinício lançado (item 51 de 16/10: conferir em que processo) - também pode justificar o fechado
        _conf = [x for tp, x in r.get("_reconc_ficha") or [] if tp == "reinicio-a-conferir"]
        if _conf and not nova:
            nova = [{"motivo": "nova prisão (a conferir)", "data": rs.fmt(_conf[-1]["entrada"]), "_conf": True}]
        # item 59 de 16/10: "alerta" só com a unidade claramente de regime fechado; com ala/anexo ou classificação incerta, "verificar"
        incerta = unidade_incerta(un) and tipo_un == "fechado"
        return [_item_rf("verificar" if nova or incerta else "alerta", "RSPE em regime %s, mas a ficha indica unidade de regime %s (%s)" % (
                             reg.split(" - ")[0].lower(), "fechado" if tipo_un != "provisorio" else "provisório", un.title()),
                         "Unidade atual%s: %s - %s. Se não houve regressão (nem cautelar) ou nova prisão, a pessoa cumpre em regime mais gravoso que o "
                         "fixado: a falta de vaga não autoriza isso - pedir a transferência ou, na falta de vaga, o regime menos gravoso/monitoramento "
                         "(STF, Súmula Vinculante 56; RE 641.320). Se houve regressão, conferir o lançamento no RSPE.%s%s" % (
                             desde, un.title(), rot, ((" A ficha registra nova prisão em %s, ainda sem reinício lançado (processo a conferir): ela pode "
                                                       "justificar o fechado ou a regressão cautelar - conferir." % nova[-1]["data"]) if nova[-1].get("_conf") else
                                                      (" O programa lançou %s pela ficha em %s: a nova prisão pode justificar o fechado ou a regressão "
                                                       "cautelar - conferir." % ((nova[-1].get("motivo") or "o reinício").split(" (")[0].lower(), nova[-1]["data"]))) if nova else "",
                             " A classificação da unidade como de regime fechado é incerta (pode ter ala de semiaberto): conferir onde a pessoa "
                             "cumpre a pena." if incerta else ""),
                         "STF, Súmula Vinculante 56; LEP, arts. 112 e 118.")]
    if reg.startswith("SEMI") and tipo_un in ("aberto", "monitoramento") or reg.startswith("ABERTO") and tipo_un == "semiaberto":
        return [_item_rf("verificar", "RSPE em regime %s; a ficha indica unidade de %s (%s)" % (reg.split(" - ")[0].lower(), tipo_un, un.title()),
                         "Unidade atual%s: %s - %s. Conferir se houve progressão, regressão ou monitoramento eletrônico não lançado no RSPE." % (desde, un.title(), rot),
                         "LEP, arts. 112, 118 e 146-B.")]
    return []


# registro de volta (recaptura, reapresentação, prisão "(evasão)") que cita a evasão sem ser a fuga
RE_RETORNO_FUGA = re.compile(r"RETORN\w*\s+(D[AE]\s+)?(EVAS|FUGA)|RECAPTURA|REAPRESENTA|APRESENTA\w*(?:-SE)? ESPONTANE|APRESENTOU-?SE ESPONTANE|\bPRES[OA]\b|MANDADO\s+(JUDICIAL\s+)?DE\s+PRIS", re.I)
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
        # a omissão favorece o assistido (sem interrupção nem falta, o período conta como cumprido e a data-base não muda): sem item
    ini_f = ev[0][0] if ev else None
    for d in fugas_r:
        if ini_f and d > ini_f and not any(abs((x - d).days) <= 30 for x, _ in fugas_f):
            # a ficha cobre a data e não registra saída/fuga: custódia contínua?
            antes = [x for x, _ in ev if d - timedelta(days=90) <= x < d]
            depois = [x for x, _ in ev if d < x <= d + timedelta(days=90)]
            livres = [x for x, t in ev if abs((x - d).days) <= 30 and (_saida_fim_custodia(t) or RE_SAIDA_OUTRA.search(t))]
            # soltura por alvará na mesma data da fuga lançada no RSPE: a saída foi legítima, não fuga
            alvara = [(x, t) for x, t in ev if abs((x - d).days) <= 1 and re.search(r"ALVAR[ÁA] DE SOLTURA|MOTIVO:\s*(ALVAR|SOLTURA)", t, re.I)
                      and not re.search(r"APRESENT", t, re.I)]  # quem se apresenta trazendo o alvará está voltando, não saindo
            if alvara:
                out.append(_item_rf("alerta", "Fuga no RSPE em %s, mas a ficha registra saída por alvará de soltura em %s" % (rs.fmt(d), rs.fmt(alvara[0][0])),
                                    "Ficha: %s. A saída foi por ordem judicial, não fuga: a fuga lançada interrompe o cumprimento, move a data-base da "
                                    "progressão, conta como falta grave (indulto, comutação, remição) e interrompe a prescrição (CP, art. 117, V). Pedir a "
                                    "retificação do evento (soltura, não fuga)." % _br(alvara[0][1])[:180],
                                    "LEP, arts. 50, II, 111 e 118; CP, arts. 113 e 117, V."))
            # saída para unidade de semiaberto/aberto pouco antes e entrada vinda de delegacia depois: a ficha confirma a evasão do
            # regime mais brando e a recaptura (a unidade de destino nem sempre registra a fuga)
            _brando = [x for x, t in ev if d - timedelta(days=30) <= x <= d + timedelta(days=3) and re.search(r"SA[ÍI]DA DA UNIDADE", t, re.I)
                       and re.search(r"DESTINO:\s*[^,]*(SEMI-?ABERTO|ABERTO|MONITORA)", t, re.I)]
            _dp_ = [x for x, t in ev if d <= x <= d + timedelta(days=120) and re.search(r"ENTRADA NA UNIDADE", t, re.I)
                    and re.search(r"PROCEDENTE:\s*[^,]*(\bD\.?P\b|DELEGACIA|DP\s|\d+\s*ª?\s*DP)", t, re.I)]
            if _brando and _dp_:
                continue
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
    # a alteração de data-base ("... DE PROGRESSÃO DE REGIME/LIVRAMENTO CONDICIONAL") não é progressão, regressão nem livramento
    incs = [i for i in r.get("_incidentes", []) if not i.get("_ficha") and not rs._negado(i) and not rs.e_alteracao_data_base(i)]
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
        # (ou até 90 dias depois: decisão lançada no SEEU depois da transferência) é a mesma
        for i in incs:
            t = rs._sem_acento(((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()).replace("-", "").replace(" ", "")
            if "PROGRESS" in t and reg_m in t:
                for c in ("data_referencia", "data_decisao"):
                    d = rs.to_date(i.get(c) or "")
                    if d and x - timedelta(days=380) <= d <= x + timedelta(days=90):
                        return True
        return False

    def regr_perto(x):
        # a ficha registra a regressão na saída para a unidade (às vezes meses depois da decisão), na ciência da decisão, no
        # mandado de prisão, no parecer do alvará ou na proposta do conselho disciplinar (antes da decisão): regressão do RSPE
        # (cautelar ou definitiva) decidida até ~1 ano antes ou até ~8 meses depois é a mesma
        for i in incs:
            t = ((i.get("tipo") or "") + " " + (i.get("complemento") or "")).upper()
            if "REGRESS" in t:
                for c in ("data_referencia", "data_decisao"):
                    d = rs.to_date(i.get(c) or "")
                    if d and x - timedelta(days=380) <= d <= x + timedelta(days=240):
                        return True
        return False

    def superada(x):
        """Marco posterior no RSPE que refez a data-base depois de x (falta homologada, regressão, nova progressão ou somatório):
        texto do primeiro, ou ""."""
        for i in sorted(incs, key=lambda i: rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") or date.min):
            d = rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "")
            if not d or d <= x + timedelta(days=30) or rs._negado(i) or rs._pendente(i):
                continue
            t = rs._rotulo_incidente(i)
            if re.search(r"FALTA GRAVE", i.get("tipo") or "", re.I) or (rs.e_incidente_regime(i) and re.search(r"REGRESS|PROGRESS|SOMAT", t, re.I)):
                return "%s em %s" % (t, rs.fmt(d))
        return ""

    def regime_rspe_em(x):
        # regime em que o RSPE põe a pessoa na data x: o do último incidente de regime (inicial, progressão, regressão,
        # somatório) até essa data
        ult = None
        for i in incs:
            if not rs.e_incidente_regime(i) or (i.get("situacao") or "CONCEDIDO") != "CONCEDIDO":
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
    # livramento concedido no RSPE antes da saída da ficha (sem revogação no meio) ou até 6 meses depois dela: a saída é a execução
    # desse livramento (o incidente pode ser lançado com outra data), não livramento ausente
    _lcs = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "") for i in r.get("_incidentes", [])
            if rs.e_concessao_livramento(i)]
    _revs = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in r.get("_incidentes", []) if rs.e_revogacao_livramento(i)]
    _lc_inc_perto = lambda x: any(d and (x <= d <= x + timedelta(days=180) or (x - timedelta(days=730) <= d < x and not any(v and d < v < x for v in _revs)))
                                  for d in _lcs)
    # registro da ficha em período que o RSPE trata como liberdade (fuga sem recaptura, soltura): progressão, regressão ou
    # livramento ali são de outra execução (a ficha é da pessoa, não do processo)
    _fora = lambda x: bool(_per) and not any(a - timedelta(days=1) <= x and (b is None or x <= b + timedelta(days=1)) for a, b in _per)
    for e in f.get("eventos", []):
        x, u = _dp(e.get("data") or ""), (e.get("texto") or "").upper()
        if not x or (_ini and x < _ini) or _fora(x):
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
            # depois dela, falta homologada ou outra alteração de regime no RSPE refez a data-base: a progressão ausente não pesa
            # mais no cálculo atual (como a progressão lançada na data errada "já superada") - informação, não alerta
            _sup = superada(x)
            out.append(("Progressão para o %s registrada na ficha em %s e ausente no RSPE%s" % (m.group(1).lower().replace(" ", ""), rs.fmt(x),
                                                                                              " - já superada" if _sup else ""),
                        "A ficha registra o cumprimento da progressão (%s). %s" % (_br(e["texto"])[:160],
                            ("Depois dela, o RSPE registra %s, que refez a data-base: a ausência não muda o cálculo atual." % _sup) if _sup else
                            "Sem o incidente no RSPE, a data-base e as frações seguintes ficam erradas: conferir a decisão e pedir o lançamento no SEEU."),
                        "info" if _sup else "alerta"))
        # saída para o monitoramento eletrônico não é regressão (a unidade registra "Motivo: Regressão de Regime" também na ida
        # ao monitoramento depois de progressão ou reconsideração)
        _dest = re.search(r"DESTINO:\s*([^,]+)", u)
        _dest_brando = bool(_dest) and classificar_unidade(_dest.group(1))[0] == "monitoramento"
        if re.search(r"REGRESS[ÃA]O", u) and "regr" not in vistos and not regr_perto(x) and not _dest_brando:
            vistos.add("regr")
            out.append(("Regressão registrada na ficha em %s e ausente no RSPE" % rs.fmt(x),
                        "Ficha: %s. Conferir se houve decisão de regressão (e a falta que a motivou) e o lançamento no SEEU." % _br(e["texto"])[:160]))
        if re.search(r"MOTIVO:\s*LIVRAMENTO CONDICIONAL|BENEFICIADO COM (O )?LIVRAMENTO", u) and "lc" not in vistos and not no_rspe(r"LIVRAMENTO", x) \
                and not _lc_ev(x) and not _lc_inc_perto(x):
            vistos.add("lc")
            # crime doloso com fato durante o período de prova (antes da prisão seguinte do RSPE): revogação obrigatória (CP, art. 86, I) e
            # o tempo em liberdade não se desconta, nem se concede novo livramento para essa pena (CP, art. 88)
            _prox = min([d for d in (rs.to_date(ev.get("data") or "") for ev in r.get("_eventos", []) if "INTERRUP" not in (ev.get("tipo") or "").upper())
                         if d and d > x] or [date.max])
            _cr = [c for c in r.get("_crimes", []) if (rs.to_date(c.get("data_infracao") or "") or date.min) > x
                   and rs.to_date(c.get("data_infracao") or "") <= _prox and not re.search(r"CULPOS", (c.get("tipo_penal") or ""), re.I)]
            _fg = [ev for ev in r.get("_eventos", []) if rs.RE_FUGA_EV.search(ev.get("motivo") or "") and rs.to_date(ev.get("data") or "")
                   and abs((rs.to_date(ev["data"]) - x).days) <= 5]
            if _cr:
                out.append(("Livramento condicional registrado na ficha em %s e ausente no RSPE" % rs.fmt(x),
                            "Ficha: %s. Durante o período de prova houve crime doloso (%s, fato em %s): a revogação é obrigatória (CP, art. 86, I) "
                            "e o tempo em liberdade não se desconta, nem se concede novo livramento para essa pena (CP, art. 88) - o período de "
                            "prova não conta. %sO SEEU não registra o livramento: conferir a decisão de revogação." % (
                                _br(e["texto"])[:160], rs.crimes_curto(_cr[:1]), _cr[0].get("data_infracao"),
                                ("O lançamento correto (livramento e revogação, no lugar da fuga lançada em %s) serve para afastar a falta de fuga. "
                                 % _fg[0]["data"]) if _fg else ""),
                            "alerta" if _fg else "verificar"))
            else:
                out.append(("Livramento condicional registrado na ficha em %s e ausente no RSPE" % rs.fmt(x),
                            "Ficha: %s. Sem o incidente no RSPE, o período de prova não é contado: pedir o lançamento no SEEU." % _br(e["texto"])[:160]))
    return [{"nivel": (o[2] if len(o) > 2 else "alerta"), "titulo": o[0], "detalhe": o[1], "fundamento": "LEP, arts. 112, 118 e 131.", "tipo": "rspe-x-ficha"}
            for o in out]


def _interrupcao_x_ficha(r, f):
    """RSPE com o cumprimento parado (último evento é interrupção): a ficha explica? Custódia depois da interrupção =
    preso (em outro processo ou sem reinício lançado), não em liberdade nem foragido; saída em liberdade = confirma."""
    out = []
    # execução extinta (o mesmo critério de rspe_view.execucao_extinta): a nova prisão da ficha é de outro processo ou sem efeito aqui -
    # não se pede retificação do RSPE desta execução
    _cr = r.get("_crimes", [])
    extinta = bool(r.get("execucao_extinta")) or (bool(_cr) and all((c.get("extinto") or "").upper().startswith("S") for c in _cr))
    for tp, x in r.get("_reconc_ficha") or []:
        if tp in ("reinicio-pela-ficha", "reinicio-a-conferir") and extinta:
            out.append({"nivel": "info", "titulo": "Nova prisão na ficha em %s, depois da interrupção do RSPE (execução extinta)" % rs.fmt(x["entrada"]),
                        "detalhe": "O RSPE termina na interrupção de %s (%s), e a ficha registra entrada%s em %s. Com a execução extinta, essa "
                                   "prisão é provavelmente de outro processo: não há reinício a pedir nesta execução." % (
                                       rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta",
                                       (" vinda de " + x["origem"]) if x["origem"] else "", rs.fmt(x["entrada"])),
                        "fundamento": "LEP, art. 111.", "tipo": "rspe-x-ficha"})
        elif tp == "reinicio-pela-ficha":
            out.append({"nivel": "alerta", "titulo": "Reinício omitido no RSPE: lançado pela ficha em %s" % rs.fmt(x["entrada"]),
                        "detalhe": "O RSPE termina na interrupção de %s (%s), sem reinício. A ficha registra entrada%s em %s e custódia desde então. "
                                   "Os cálculos do programa (situação, custódia, prescrição, incisos do indulto) passam a considerar o cumprimento a "
                                   "partir de %s. Pedir a retificação do RSPE (reinício/recaptura) - sem ele, o SEEU não projeta progressão nem livramento." % (
                                       rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta",
                                       (" vinda de " + x["origem"]) if x["origem"] else "", rs.fmt(x["entrada"]), rs.fmt(x["entrada"])),
                        "fundamento": "LEP, arts. 111 e 112; CP, arts. 113 e 117, V.", "tipo": "rspe-x-ficha"})
        elif tp == "reinicio-a-conferir":
            out.append({"nivel": "verificar", "titulo": "Nova prisão na ficha em %s, depois da interrupção do RSPE (%s): conferir em que processo" % (
                            rs.fmt(x["entrada"]), x["motivo"].lower() or "motivo não consta"),
                        "detalhe": "O RSPE termina na interrupção de %s (%s), e a ficha registra entrada%s em %s e custódia desde então. A prisão "
                                   "pode ser desta execução (reinício do cumprimento, a pedir a retificação do RSPE) ou de outro processo (suspensão "
                                   "desta execução, sem curso da prescrição - CP, art. 116, p. único). Reinício e suspensão levam a data-base e a "
                                   "prescrição a resultados opostos: o programa não lança o reinício até a conferência do processo da prisão." % (
                                       rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta",
                                       (" vinda de " + x["origem"]) if x["origem"] else "", rs.fmt(x["entrada"])),
                        "fundamento": "LEP, arts. 111 e 112; CP, arts. 116, p. único, e 117, V.", "tipo": "rspe-x-ficha"})
        elif tp == "custodia-outra-execucao":
            out.append({"nivel": "verificar", "titulo": "Custódia desde %s serviu a outra execução até %s: cumprimento desta lançado em %s" % (
                            rs.fmt(x["entrada"]), rs.fmt(x["extincao"]), rs.fmt(x["extincao"] + timedelta(days=1))),
                        "detalhe": "A ficha registra a prisão em %s e a extinção da pena da execução %s em %s, com a pessoa presa. Até essa data a "
                                   "custódia foi o cumprimento daquela pena, e o tempo já usado numa pena não se detrai de novo (CP, art. 42). Os "
                                   "cálculos do programa contam esta execução a partir de %s. Conferir a guia e o início do cumprimento lançado no SEEU." % (
                                       rs.fmt(x["entrada"]), x["autos"], rs.fmt(x["extincao"]), rs.fmt(x["extincao"] + timedelta(days=1))),
                        "fundamento": "CP, art. 42; LEP, arts. 106 e 111.", "tipo": "rspe-x-ficha"})
        elif tp == "custodia-nao-desta":
            civil = x.get("tipo") == "civil"
            out.append({"nivel": "info" if (civil or extinta) else "verificar",
                        "titulo": "Prisão na ficha em %s não lançada como %s desta execução: %s" % (
                            rs.fmt(x["entrada"]), "reinício" if x.get("interrupcao") else "início", "prisão civil" if civil else "outro processo"),
                        "detalhe": "%s%s. %s" % (
                            ("O RSPE termina na interrupção de %s (%s). " % (rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta"))
                            if x.get("interrupcao") else "O RSPE não tem evento de prisão. ",
                            x["texto"][0].upper() + x["texto"][1:],
                            "A prisão civil não conta como pena nem como detração: o cumprimento desta execução não começou por ela." if civil else
                            "Com a execução %s no SEEU, essa prisão não é o cumprimento desta pena; pode valer como detração (CP, art. 42) se o fato "
                            "desta execução for anterior a ela e o tempo não for usado na condenação do outro processo - conferir." % (
                                "extinta" if extinta else "suspensa ou arquivada")),
                        "fundamento": "CP, art. 42; LEP, art. 111.", "tipo": "rspe-x-ficha"})
        elif tp == "inicio-pela-ficha":
            out.append({"nivel": "alerta", "titulo": "RSPE sem evento de prisão: início lançado pela ficha em %s" % rs.fmt(x["entrada"]),
                        "detalhe": "O RSPE não lista eventos de início do cumprimento; a ficha registra a prisão/entrada no sistema prisional em %s. "
                                   "Os cálculos do programa passam a considerar a custódia desde essa data. Conferir a guia e pedir a retificação do RSPE." % rs.fmt(x["entrada"]),
                        "fundamento": "LEP, arts. 105 e 106; CP, art. 42.", "tipo": "rspe-x-ficha"})
        elif tp == "reinicio-divergente":
            dias = (x["reinicio"] - x["entrada"]).days
            if any(a <= x["entrada"] <= b for a, b in _soltura_x_ficha(r, f, so_periodos=True)):
                continue  # dentro da interrupção sem soltura na ficha: o item dela já conta esses dias
            _ext = penas_extintas_no_periodo(r, x["entrada"], x["reinicio"])
            if _ext:
                out.append({"nivel": "verificar", "titulo": "Entrada na ficha em %s, antes do reinício no RSPE (%s): provável cumprimento das penas extintas" % (
                                rs.fmt(x["entrada"]), rs.fmt(x["reinicio"])),
                            "detalhe": "Depois da interrupção de %s (%s), a ficha registra entrada no sistema prisional em %s; o RSPE só reinicia o "
                                       "cumprimento em %s. Nesse intervalo terminaram penas desta execução (%s): a custódia provavelmente foi o "
                                       "cumprimento delas e não falta na conta. Conferir na decisão de extinção." % (
                                           rs.fmt(x["interrupcao"]), x["motivo"].lower() or "motivo não consta", rs.fmt(x["entrada"]),
                                           rs.fmt(x["reinicio"]), _ext),
                            "fundamento": "CP, art. 42; LEP, art. 111.", "tipo": "rspe-x-ficha"})
                continue
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
    if ok is None and txt:
        # saída por determinação judicial de destino incerto, sem nova entrada: nem liberdade nem custódia afirmadas
        return out + [{"nivel": "verificar", "titulo": "Cumprimento interrompido em %s: saída por determinação judicial na ficha, a conferir" % rs.fmt(d),
                       "detalhe": "Motivo no RSPE: %s. Ficha: %s. A saída por determinação judicial não é liberdade automática: conferir nos autos "
                                  "se foi soltura, transferência para outra comarca ou cumprimento em outro regime." % (mot.lower() or "não consta", txt),
                       "fundamento": "LEP, art. 111; CP, arts. 113 e 116, p. único.", "tipo": "rspe-x-ficha"}]
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
    if ok and (extinta or any(tp in ("reinicio-a-conferir", "custodia-nao-desta") for tp, _x in r.get("_reconc_ficha") or [])):
        return out  # nova prisão depois de liberdade provisória/aberto, de outro processo ou em execução extinta: o item acima já trata
    if ok:
        return out + [{"nivel": "alerta", "titulo": "RSPE indica pena interrompida em %s, mas a ficha registra custódia" % rs.fmt(d),
                 "detalhe": "Motivo no RSPE: %s. Ficha: %s, sem entrada vinda de fora depois da interrupção (custódia contínua). A pessoa está presa: provável prisão em outro processo (suspensão, sem curso da prescrição - "
                            "CP, art. 116, p. único) ou reinício do cumprimento não lançado. Conferir e pedir a retificação do RSPE (reinício ou "
                            "unificação), que destrava progressão e livramento." % (mot.lower() or "não consta", txt),
                 "fundamento": "LEP, arts. 111 e 112; CP, art. 116, p. único.", "tipo": "rspe-x-ficha"}]
    return out + [{"nivel": "info", "titulo": "Interrupção de %s confirmada pela ficha: %s" % (rs.fmt(d), txt),
             "detalhe": "Motivo no RSPE: %s. A ficha registra a saída do sistema prisional depois da interrupção." % (mot.lower() or "não consta"), "fundamento": "CP, art. 113.", "tipo": "rspe-x-ficha"}]


# fato do histórico anterior que pode mudar a custódia ininterrupta ou a prescrição: evasão/fuga, soltura, prisão, PAD/falta,
# progressão/regressão, transferência de regime
_RE_HIST_RELEVANTE = re.compile(r"EVADI|EVASAO|\bFUGA|FORAGID|NAO RETORNOU|ALVARA|SOLTURA|LIBERDADE|LIVRAMENTO|\bPRES[OA]\b|FLAGRANTE|"
                                r"RECAPTUR|PADIC?\b|PROCESSO DISCIPLINAR|FALTA|CELA DISCIPLINAR|ISOLAD|PROGRESS|REGRESS|SEMI-?ABERTO|ABERTO")


def historico_anterior(f):
    """Histórico anterior ao SIAPEN (bloco em 10 pt cortado na impressão, guardado em historico_oculto): só exibição, fora das
    contas. Cada "Em dd/mm/aa" com a sua data. Devolve [{data (date ou None), texto, relevante}]."""
    linhas = [" ".join((x or "").split()) for x in (f or {}).get("historico_oculto") or []]
    txt = " ".join(x for x in linhas if x)
    if not txt:
        return []
    out = []
    partes = re.split(r"(?:^|(?<=[\s.;,>]))(?=Em \d{1,2}/\d{1,2}/\d{2,4}\b)", txt)
    for p_ in partes:
        p_ = p_.strip(" -;>")
        if not p_:
            continue
        m = re.match(r"Em (\d{1,2})/(\d{1,2})/(\d{2,4})\b", p_)
        d = None
        if m:
            aa = int(m.group(3))
            aa = aa + (2000 if aa < 70 else 1900) if aa < 100 else aa
            d = _dp("%02d.%02d.%d" % (int(m.group(1)), int(m.group(2)), aa))
        out.append({"data": d, "texto": p_, "relevante": bool(_RE_HIST_RELEVANTE.search(rs._sem_acento(p_).upper()))})
    return out


def _historico_anterior_x_ficha(r, f):
    """Histórico anterior ao SIAPEN: exibido como informação, sem lançar as evasões, PADs e progressões nas contas. "A conferir"
    (verificar) só quando um fato desses cai no período desta execução (pode mudar a custódia ininterrupta do indulto ou a prescrição)."""
    H = historico_anterior(f)
    if not H:
        return []
    ds = [h["data"] for h in H if h["data"]]
    ini = min([d for d in (rs.to_date(e.get("data") or "") for e in r.get("_eventos", [])) if d] or [None], key=lambda x: x or date.max)
    conferir = [h for h in H if h["relevante"] and h["data"] and ini and h["data"] >= ini]
    per = ("de %s a %s" % (rs.fmt(min(ds)), rs.fmt(max(ds)))) if ds else "sem datas legíveis"
    lista = "; ".join("%s: %s" % (rs.fmt(h["data"]) if h["data"] else "sem data", _br(h["texto"])[:140]) for h in (conferir or H)[:12])
    if conferir:
        return [_item_rf("verificar", "Histórico anterior ao SIAPEN com %s no período desta execução - a conferir" % rs.pl(len(conferir), "fato", "fatos"),
                         "A ficha traz um histórico anterior ao SIAPEN (%s), cortado na impressão, que não entra nas contas. Estes fatos caem "
                         "depois do início desta execução (%s) e podem mudar a custódia ininterrupta do indulto ou a prescrição: %s. "
                         "Conferir nos autos antes de usá-los." % (per, rs.fmt(ini), lista),
                         "Ficha disciplinar (SIAPEN); LEP, art. 111; CP, arts. 113 e 117.")]
    return [_item_rf("info", "Histórico anterior ao SIAPEN (%s): só exibido, fora das contas" % per,
                     "A ficha traz um bloco anterior ao SIAPEN, cortado na impressão (%s). Ele não é lançado como evasão, falta ou "
                     "progressão nas contas desta execução: %s." % (rs.pl(len(H), "registro", "registros"), lista),
                     "Ficha disciplinar (SIAPEN).")]


def _faltas_outra_execucao_x_ficha(r, f):
    """Faltas da ficha anteriores ao início desta execução (a ficha cobre toda a vida prisional): só informação - não entram como
    falta a apurar nem nas janelas dos decretos (decisão: contar só as faltas desta execução, dentro do prazo de reabilitação)."""
    ini = min([d for d in (rs.to_date(e.get("data") or "") for e in r.get("_eventos", []) if not e.get("_ficha")) if d] or [None],
              key=lambda x: x or date.max)
    if not ini:
        return []
    ant = [x for x in f.get("faltas", []) if x.get("grave") and x.get("situacao") != "arquivada"
           and (_dp(x.get("data_fato") or "") or _dp(x.get("data_registro") or "") or date.max) < ini]
    if not ant:
        return []
    return [_item_rf("info", "Ficha: %s anterior%s ao início desta execução (%s) - só informação" % (
        rs.pl(len(ant), "falta grave", "faltas graves"), "es" if len(ant) > 1 else "", rs.fmt(ini)),
        "A ficha cobre toda a vida prisional. Estas faltas são de execução anterior e não entram como falta a apurar, nem nas janelas "
        "dos decretos: %s. Em reinício ou unificação, conferir nos autos se alguma é desta pena." % "; ".join(
            "%s%s (%s)" % (_br(x.get("data_fato") or x.get("data_registro") or ""), (" - " + x["artigo"]) if x.get("artigo") else "", x.get("situacao") or "registrada")
            for x in ant[:10]),
        "LEP, art. 112, § 7º (reabilitação da conduta); decretos de indulto, art. 6º.")]


def _falta_anterior_x_perda(r, f):
    """Falta grave anterior registrada na ficha (e sem homologação no RSPE) x perda de dias remidos por falta posterior:
    pelo art. 127 da LEP, a nova perda não alcança a remição adquirida antes da falta anterior."""
    import rspe_auditoria as ra
    res, faltas_rspe, _ = ra.perdas_por_falta([i for i in r.get("_incidentes", []) if not i.get("_ficha")])
    if not res:
        return []
    incs = remicoes_rspe(r)
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
                          "detalhe": "A ficha registra falta grave de %s (%s, decisão do conselho em %s) que não consta homologada no RSPE. Se o juízo a homologou "
                                     "e decretou a perda de dias remidos (o art. 127 liga o recomeço da contagem à revogação dos dias), a contagem da remição "
                                     "recomeçou nessa data e a perda aplicada pela falta de %s não poderia alcançar a remição do trabalho anterior: %s. "
                                     "Conferir a homologação e a perda e, se houver, impugnar o cálculo (desconto em duplicidade)." % (
                                         fa0["data_fato"], fa0.get("artigo") or "art. n/i", fa0.get("data_resultado") or "?", rs.fmt(fk), "; ".join(partes)),
                          "fundamento": ra.FUND_127})
    return itens


def resumo(f):
    if not f:
        return ""
    trab = f.get("trabalho", [])
    em = [x for x in trab if not x.get("fim") and not x.get("so_lancamento")]
    return "%s, %s remidos · %s" % (
        rs.pl(len(f.get("atestados", [])), "atestado", "atestados"), _dias_txt(f.get("dias_remidos_atestados") or 0),
        ("trabalhando em " + (em[-1].get("empresa") or em[-1].get("setor") or "?") + " desde " + em[-1]["inicio"]) if em else "sem trabalho em curso")


def _fmtn(v):
    v = float(v)
    # até 0,01 do inteiro, o inteiro mais próximo (39,99 -> 40, como o SEEU lança a remição do atestado de 39,99); o "%d" truncava
    # (39,99 -> 39) e a tolerância dependia do arredondamento binário (39,99 virava 39; 66,99 ficava 66,99)
    return ("%d" % round(v)) if abs(v - round(v)) < 0.01 + 1e-9 else ("%.2f" % v).replace(".", ",")


# ---------------------------------------------------------------- trabalho por emprego x remição no RSPE

def _norm(t):
    t = (t or "").upper()
    t = re.sub(r"^(PP|CC|A1|R1)\s*-\s*", "", t)
    t = re.sub(r"[-/]?\s*(CPAIG|IPCG|CPAG)\b", "", t)
    return re.sub(r"\W", "", t)


def _sem_setores_baixados(t, eventos):
    """Vínculo em curso que junta setores abertos no mesmo dia ("FABRICA / EMPRESA X"): tira do nome o setor com baixa posterior
    na ficha ("Trabalho: Deixa de trabalhar, no setor de trabalho FABRICA ...") - o trabalho atual é só o que segue aberto."""
    sets = t.get("setores") or []
    ti = _dp(t.get("inicio") or "")
    if len(sets) < 2 or not ti:
        return t
    norm = lambda x: re.sub(r"\W", "", rs._sem_acento(x or "").upper())
    baix = set()
    for e in eventos:
        d = _dp(e.get("data") or "")
        u = rs._sem_acento(e.get("texto") or "").upper()
        mm = re.match(r"\s*TRABALHO:\s*DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.*?)(?:,|$)", u)
        if d and d > ti and mm:
            baix.add(norm(mm.group(1)))
    resto = [x for x in sets if norm(x) not in baix]
    if not resto or len(resto) == len(sets):
        return t
    t2 = dict(t, setor=" / ".join(resto), setores=resto)
    if t2.get("empresa") and " / " in t2["empresa"]:
        t2["empresa"] = " / ".join(x for x in t2["empresa"].split(" / ") if norm(x) not in baix) or t2["empresa"]
    return t2


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


HORAS_DIA_ESTUDO = 4  # estimativa: as certidões da EJA atestam 400 h em 100 dias letivos


# recesso escolar descontado da estimativa do estudo (sem carga horária declarada): janeiro, a segunda quinzena de julho e de 20 a 31 de
# dezembro - o que deixa cerca de 200 dias letivos por ano (LDB, art. 24, I). Editável na base jurídica: remicao.recesso_escolar,
# lista de "MM-DD/MM-DD"
RECESSO_ESCOLAR = ["01-01/01-31", "07-16/07-31", "12-20/12-31"]


def em_recesso(d):
    """O dia d cai no recesso escolar (RECESSO_ESCOLAR ou a base jurídica)?"""
    lst = RECESSO_ESCOLAR
    try:
        import rspe_regras as _rg
        lst = ((_rg.carregar() or {}).get("remicao") or {}).get("recesso_escolar") or RECESSO_ESCOLAR
    except Exception:
        pass
    k = (d.month, d.day)
    for x in lst:
        try:
            i_, f_ = (tuple(int(v) for v in p.split("-")[:2]) for p in str(x).split("/")[:2])
        except ValueError:
            continue
        if i_ <= k <= f_:
            return True
    return False


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


def dias_jornada_set(a, b, jornada="", ref=None):
    """Dias de trabalho entre a e b (inclusive), como conjunto, pela jornada (a mesma regra de dias_trabalho). Na 12x36, dia sim, dia
    não a partir de ref (o início do vínculo; sem ele, a)."""
    if not a or not b or b < a:
        return set()
    if jornada in ("12x36", "todos"):
        r0 = ref or a
        return {a + timedelta(days=k) for k in range((b - a).days + 1)
                if jornada == "todos" or ((a + timedelta(days=k)) - r0).days % 2 == 0}
    lim = 5 if jornada == "seg-sex" else 6
    fer = set()
    for y in range(a.year, b.year + 1):
        fer |= feriados(y)
    return {a + timedelta(days=k) for k in range((b - a).days + 1) if (a + timedelta(days=k)).weekday() < lim and a + timedelta(days=k) not in fer}


ORDEM_ESTIMATIVA = ["sem_atestado", "ficta", "em_curso", "a_conferir"]


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
    import rspe_remicao as _rr
    return _rr.com_siglas((nome or "").strip().title())


def linha_unidades(f):
    """[(data, unidade)] das entradas em unidade penal registradas na ficha: a estruturada ("Entrada na Unidade Penal: X, Procedente";
    "Entrada no Regime Semiaberto da Unidade Penal: X, Procedente")
    e a das fichas antigas, pela sigla ("ENTRADA NO IPCG PROCEDENTE DA ...", "DEU ENTRADA NO EPJFC", "INGRESSOU NO PTRAN")."""
    out = []
    for e in f.get("eventos", []):
        # ("Entrada no Regime Semiaberto da Unidade Penal: X, Procedente" é a mesma entrada estruturada)
        m = re.search(r"Entrada n[oa] (?:Regime [\w-]+ da )?Unidade Penal:\s*(.+?),\s*Procedente", e.get("texto") or "", re.I) or \
            re.search(r"^\W*(?:(?:NESTA DATA\W*)?(?:DEU ENTRADA|ENTRADA|(?:RE)?INGRESSOU|ADENTROU))\s+N[OA]\s+(?!UNIDADE\b|REGIME\b|SISTEMA\b|PRESIDIO\b)"
                      r"([A-Z][A-Z]{1,7})\b\W{0,3}(?:,|-|PROCEDENTE|ORIUNDO|VINDO|CONF|$)", rs._sem_acento(e.get("texto") or "").upper())
        d = _dp(e.get("data") or "")
        if m and d:
            nome = re.sub(r'["“”]', "", m.group(1)).strip()
            if not out or out[-1][1] != nome or out[-1][0] != d:
                out.append((d, nome))
    out.sort(key=lambda x: x[0])
    return out


_UN_GENERICAS = {"PENITENCIARIA", "ESTABELECIMENTO", "PENAL", "PRESIDIO", "EP", "DE", "DA", "DO", "DOS", "DAS", "E", "UNIDADE"}


def _mesma_unidade(a, b):
    """Grafias da mesma unidade ("PENITENCIÁRIA JAIR FERREIRA DE CARVALHO" x "EPJFC"; "... ESTADUAL" x "... ESTADUAL DE CAMPO GRANDE")."""
    na, nb = [re.sub(r"[^A-Z0-9 ]", " ", rs._sem_acento(x or "").upper()).split() for x in (a, b)]
    if not na or not nb:
        return False
    ja, jb = "".join(na), "".join(nb)
    if ja == jb or nome_unidade(a) == nome_unidade(b) or ja.startswith(jb) or jb.startswith(ja):
        return True
    sa, sb = sigla_unidade(a), sigla_unidade(b)
    if sa == sb and sa.isupper() and len(sa) <= 8:
        return True
    ini_a, ini_b = "".join(w[0] for w in na if w not in ("DE", "DA", "DO", "DOS", "DAS", "E")), \
        "".join(w[0] for w in nb if w not in ("DE", "DA", "DO", "DOS", "DAS", "E"))
    if (len(na) == 1 and na[0] == ini_b) or (len(nb) == 1 and nb[0] == ini_a):
        return True  # sigla x nome por extenso ("EPMC" x "ESTABELECIMENTO PENAL MASCULINO DE COXIM")
    ca, cb = {w for w in na if w not in _UN_GENERICAS}, {w for w in nb if w not in _UN_GENERICAS}
    return bool(ca) and ca == cb


def linha_unidades_exibicao(f):
    """linha_unidades com as unidades deduzidas das saídas ("Saída da Unidade Penal: X, Destino: ..."): a saída mostra que a pessoa
    estava em X; sem a entrada em X registrada, X passa a valer desde a primeira mudança de cela em X depois do marco anterior
    (entrada ou saída) ou, se o marco anterior é uma saída (ou não há marco), desde ele. Só para EXIBIR a unidade: a conta da
    remição, a custódia e a divisão dos dias por unidade seguem com linha_unidades (só as entradas)."""
    tl = linha_unidades(f)
    evs = [(e, _dp(e.get("data") or "")) for e in f.get("eventos", [])]
    evs = [(e, d) for e, d in evs if d]
    saidas = []
    for e, d in evs:
        m = re.search(r"Sa[íi]da da Unidade Penal:\s*(.+?),\s*Destino", e.get("texto") or "", re.I)
        if m and re.sub(r'["“”]', "", m.group(1)).strip():
            saidas.append((d, re.sub(r'["“”]', "", m.group(1)).strip()))
    novos = []
    for k, (d, x) in enumerate(saidas):
        ant = [(a, u) for a, u in sorted(tl + novos, key=lambda y: y[0]) if a < d]
        if ant and _mesma_unidade(ant[-1][1], x):
            continue
        s_ant = [a for a, _u in saidas[:k] if a < d]
        marco_e = ant[-1][0] if ant else None
        marco_s = s_ant[-1] if s_ant else None
        marco = max([m_ for m_ in (marco_e, marco_s) if m_], default=None)
        # primeira mudança de cela registrada em X depois do marco: a pessoa já estava lá
        cela = next((dd for e, dd in evs if (marco is None or dd >= marco) and dd < d and
                     (lambda mc: mc and _mesma_unidade(mc.group(1), x))(re.match(r"\W*Mudan[çc]a de Cela:\s*([^,]+),", e.get("texto") or "", re.I))), None)
        if cela:
            ini = cela
        elif marco is None:
            ini = evs[0][1] if evs and evs[0][1] < d else None
        elif marco_s and (not marco_e or marco_s > marco_e):
            ini = marco_s  # saída anterior sem entrada registrada depois: a pessoa foi para X
        else:
            ini = None  # entrada em outra unidade sem a saída dela: não se sabe quando passou para X
        if ini:
            novos.append((ini, x))
    if not novos:
        return tl
    return sorted(tl + novos, key=lambda y: y[0])


SEM_UNIDADE = "Unidade não identificada na ficha"

# grafias da mesma unidade na ficha (sigla, abreviação, nome antigo): um nome só no relatório por unidade
UNIDADES_CANON = [
    (r"^CT$|CENTRO DE TRIAGEM", "Centro de Triagem Anísio Lima"),
    (r"^CPAI?G?$|AGROINDUSTRIAL DA GAMELEIRA", "Centro Penal Agroindustrial da Gameleira"),  # CPA, CPAG, CPAIG ("CPA da Gameleira")
    (r"GAMELEIRA II\b", "Penitenciária Estadual Masculina de Regime Fechado da Gameleira II"),
    (r"(PENIT\.? EST\.? MASC\.?|PENITENCI[AÁ]RIA ESTADUAL MASCULINA) DE REGIME FECHADO DA GAMELEIRA$",
     "Penitenciária Estadual Masculina de Regime Fechado da Gameleira"),
    (r"^E?PJFC$|JAIR FERREIRA DE CARVALHO", "Estabelecimento Penal Jair Ferreira de Carvalho"),
    (r"^PSMTL$|SEGURANCA MEDIA DE TRES LAGOAS", "Penitenciária de Segurança Média de Três Lagoas"),
    (r"^EPMC$|ESTABELECIMENTO PENAL MASCULINO DE COXIM", "Estabelecimento Penal Masculino de Coxim"),
    (r"^EPRACA$|REGIME ABERTO E CASA (DO )?ALBERGADO", "Estabelecimento Penal de Regime Aberto e Casa do Albergado de Campo Grande"),
    (r"^IPCG$|INSTITUTO PENAL DE CAMPO GRANDE", "Instituto Penal de Campo Grande"),
    (r"^PTRAN$|PRES[IÍ]DIO DE TR[AÂ]NSITO", "Presídio de Trânsito de Campo Grande"),
    (r"MONITORAMENTO VIRTUAL", "Unidade Mista de Monitoramento Virtual Estadual de Campo Grande"),
    (r"^PDIB$|PENITENCIARIA DE DOIS IRMAOS? DO BURITI", "Penitenciária de Dois Irmãos do Buriti"),  # o SIAPEN grafa "Dois Irmão"
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
    import rspe_remicao as _rr
    return " ".join(w.lower() if w in lig and k else w if w in _rr.SIGLAS else w.capitalize()
                    for k, w in enumerate((nome or "").strip().upper().split()))


def _data_local_doc(d, linhas=None):
    """(7.14.5) Data que dá a unidade do documento: o fim do período atestado (o trabalho foi feito lá - "366/2025/ST/PED", emitido já
    em outra unidade, é da PED), e não a emissão; sem período no texto, o fim do trabalho da ficha ligado a ele (sugerido); sem nada
    disso, a emissão."""
    fims = [b for _a, b in d.get("_segs") or [] if b]
    if not fims:
        ps = (d.get("periodo") or "").split(" a ")
        fims = [x for x in [rs.to_date(ps[-1].strip())] if x] if len(ps) == 2 else []
    if not fims and d.get("chave"):
        # o início do último trabalho ligado (a unidade da linha de trabalho é a do início dela)
        fims = [L["ini"] + timedelta(days=1) for L in linhas or [] if L.get("at_chave") == d["chave"] and L.get("ini")]
    fim = max(fims) - timedelta(days=1) if fims else None  # o último dia do período pode ser o da transferência
    return min(fim, d["emissao"]) if fim and d.get("emissao") else (fim or d.get("emissao"))


def _unidade_em(tl, d):
    u = SEM_UNIDADE
    for e, x in tl or []:
        if d and e <= d:
            u = nome_unidade(x)
    return u


def _prio_127(rot_):
    """Ordem das faltas na ressalva do art. 127: homologada, evasão do RSPE, pendente de homologação, só registrada na ficha."""
    return 0 if "homologada" in rot_ and "pendente" not in rot_ else 1 if rot_.startswith("evasão") else 2 if "pendente" in rot_ else 3


def _dias_txt(v):
    """'1 dia' / '2,5 dias' / '3 dias'."""
    return "%s %s" % (_fmtn(v), "dia" if _fmtn(v) == "1" else "dias")


def _br(txt):
    """dd.mm.aaaa e dd/mm/aa -> dd/mm/aaaa."""
    txt = re.sub(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", r"\1/\2/\3", txt or "")
    return re.sub(r"\b(\d{2})/(\d{2})/(\d{2})\b(?!/|\d)", lambda m: "%s/%s/%s" % (m.group(1), m.group(2), (2000 if int(m.group(3)) < 70 else 1900) + int(m.group(3))), txt)


def _lista_e(itens):
    itens = [x for x in itens if x]
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1] if itens else ""


def fundamentacao_remicao(res, r=None):
    """Fundamentação do pedido de remição: divergência entre a ficha disciplinar (SIAPEN) e o RSPE no trabalho (atestados sem
    remição, trabalho sem atestado) e no estudo (frequência, ENCCEJA/ENEM, leitura); o ônus de reunir os atestados é da
    administração (LEP, art. 129); pedidos de declaração, de certificação pela unidade e de atualização do cálculo; reflexo na
    progressão. O que depende de conferência fica entre colchetes."""
    ats = res.get("atestados_pendentes") or []
    est_h = res.get("estudo_horas_pend") or 0
    exames, leituras = res.get("exames_f") or [], res.get("leituras_f") or []
    sem_at = res.get("sem_atestado_f") or []
    if not ats and est_h < 12 and not exames and not leituras and not sem_at and not res.get("educacao_f"):
        return ""
    r = r or {}
    par, total = [], 0.0
    if ats:
        total = round(sum(a["dias_remidos"] for a in ats), 2)
        todos_trab = all(a["dias_trabalhados"] for a in ats)
        # atestado inteiro sem remição (nem parte já remida, nem acima do possível): pede-se 1/3 dos dias trabalhados - o atestado
        # que declara menos (fração truncada, erro de conta) não reduz o pedido; o que declara mais (arredondamento) fica com o que declara
        parcial = [a for a in ats if a.get("ja_remidos") or a.get("acima_do_possivel")]
        cheios = [a for a in ats if a not in parcial]
        trab = sum(a["dias_trabalhados"] for a in cheios)
        menos = [a for a in cheios if a["dias_remidos"] <= a["dias_trabalhados"] / 3 - 1]
        acima = [a for a in cheios if a["dias_remidos"] > a["dias_trabalhados"] / 3 + 0.01]
        if todos_trab:
            total = round(sum(max(a["dias_remidos"], a["dias_trabalhados"] / 3) for a in cheios) + sum(a["dias_remidos"] for a in parcial), 2)
        _n = lambda a: (a.get("numero") or "s/n").split("/ST")[0]

        def _item(a):
            per = (", referente ao período de %s a %s" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else ""
            dt_ = ("%s trabalhados e " % _dias_txt(a["dias_trabalhados"])) if a["dias_trabalhados"] else ""
            obs = ""
            if a.get("ja_remidos"):
                obs = " - dos quais só ≈ %s fora do período já remido (%s)" % (_dias_txt(a["dias_remidos"]), a["ja_remidos"])
            elif a.get("acima_do_possivel"):
                obs = " - acima do possível no período: requerem-se ≈ %s, a conferir no atestado" % _dias_txt(a["dias_remidos"])
            return "nº %s, de %s%s, com %s%s remidos%s" % (_n(a), _br(a["data"]), per, dt_, _dias_txt(a.get("dias_atestado") or a["dias_remidos"]), obs)
        txt = ("A ficha disciplinar do SIAPEN registra %s de trabalho %s (LEP, art. 126, § 1º, II). O RSPE, contudo, não registra remição "
               "correspondente." % ("o atestado" if len(ats) == 1 else "os atestados", "; ".join(_item(a) for a in ats)))
        razao = "à razão de 1 dia de pena a cada 3 de trabalho (LEP, art. 126, § 1º, II)"
        if todos_trab:
            if len(ats) > 1 and cheios:
                txt += " Os %s trabalhados, %s, correspondem a %s remidos." % (_dias_txt(trab), razao, _dias_txt(round(trab / 3, 2)))
            if acima:
                txt += " %s, acima de 1/3 (arredondamento): requer-se o valor declarado." % (
                    "; ".join("O atestado nº %s declara %s remidos para %s trabalhados" % (_n(a), _fmtn(a["dias_remidos"]), _fmtn(a["dias_trabalhados"]))
                              for a in acima))
            if menos:
                txt += " %s menos que 1/3 dos dias trabalhados (%s): requer-se a proporção legal." % (
                    "Os atestados declaram" if len(menos) > 1 else "O atestado declara",
                    "; ".join("nº %s: %s remidos para %s trabalhados" % (_n(a), _fmtn(a["dias_remidos"]), _fmtn(a["dias_trabalhados"])) for a in menos))
            if parcial and cheios or acima or menos:
                txt += " No total, %s remidos." % _dias_txt(total)
        else:
            # sem os dias trabalhados na ficha, a conta "1 a cada 3" não se demonstra: vale o que o atestado declara
            txt += " %s %s remidos." % ("Os atestados declaram" if len(ats) > 1 else "O atestado declara", _dias_txt(total))
        par.append(txt)
    if sem_at:
        par.append(("A ficha registra, ainda, trabalho sem atestado emitido: %s." if ats else
                    "A ficha disciplinar do SIAPEN registra trabalho sem atestado emitido nem remição correspondente no RSPE: %s.") % "; ".join(sem_at))
    # estudo: frequência escolar, certificação (ENCCEJA/ENEM) e leitura
    est = []
    if est_h >= 12:
        cursos = "; ".join("%s (%s%s)" % (e["curso"].title(), _br(e["inicio"]), (" a " + _br(e["fim"])) if e.get("fim") else " em diante")
                           for e in res.get("estudos_pendentes") or [])
        est.append("matrícula em estudo sem remição no RSPE%s, a ser comprovada por certidão de frequência, para a remição à razão de "
                   "1 dia de pena a cada 12 horas de frequência escolar, divididas em no mínimo 3 dias (LEP, art. 126, § 1º, I)"
                   % ((": " + cursos) if cursos else ""))
    if exames:
        est.append("aprovação %s, que %s remição pelo estudo tomando por base 50%% da carga horária definida legalmente para cada nível de "
                   "ensino - 1.600 horas para os anos finais do ensino fundamental e 1.200 horas para o ensino médio -, acrescida de 1/3 "
                   "por conclusão de nível de educação (Res. CNJ 391/2021, art. 3º, parágrafo único; LEP, art. 126, §§ 1º, I, e 5º)" % (_lista_e(
                       ["no %s (certificado registrado em %s)" % (x["exame"], _br(x["data"])) for x in exames]), "geram" if len(exames) > 1 else "gera"))
    if leituras:
        # leitura remida em parte: pede-se só a diferença (as obras que a decisão não alcançou), a conferir na decisão
        est.append("relatórios de leitura peticionados em %s sem remição correspondente no RSPE, à razão de 4 dias por obra lida, até 12 "
                   "obras em 12 meses (Res. CNJ 391/2021, art. 5º, V)" % _lista_e(
                       ["%s%s" % (_br(x["data"]), (" (%s ainda sem remição; o restante já remido)" % rs.pl(x["obras"], "obra", "obras")) if x.get("parcial") and x["obras"] else
                                  (" (%s)" % rs.pl(x["obras"], "obra", "obras")) if x["obras"] else "") for x in leituras]))
    edu_ = res.get("educacao_f") or []
    if edu_:
        est.append("%s sem remição correspondente no RSPE, à razão de 1 dia de pena a cada 12 horas de estudo (LEP, art. 126, § 1º, I), "
                   "conforme a carga horária certificada" % _lista_e(["%s, peticionad%s em %s" % (
                       o["rotulo"].replace("Certidão de frequência escolar", "certidão de frequência escolar").replace("Curso de qualificação", "curso de qualificação")
                       .replace("Atestado de estudo", "atestado de estudo"),
                       "a" if o["tipo"] == "certidao" else "o", rs.fmt(o["data"])) for o in edu_]))
    if est:
        par.append(("Quanto ao estudo, a ficha registra " if (ats or sem_at) else "A ficha disciplinar do SIAPEN registra ") +
                   "; ".join(est) + (". Caso a remição correspondente ainda não tenha sido declarada, deve sê-lo." if exames else "."))
    uns = res.get("unidades_f") or []
    par.append("A divergência indica que nem todos os atestados de trabalho e estudo produzidos pela administração penitenciária chegaram aos "
               "autos ou foram apreciados.%s Exigir que a defesa requisite, unidade por unidade, cada atestado faltante transfere ao apenado "
               "um ônus que é da administração." % ((" O apenado cumpriu pena em mais de uma unidade prisional (%s), o que fragmenta os registros."
                                                    % _lista_e(uns)) if len(uns) > 1 else ""))
    par.append("Compete à autoridade administrativa encaminhar mensalmente ao juízo da execução cópia do registro dos condenados que trabalham "
               "ou estudam, com os dias de trabalho e as horas de frequência escolar de cada um (LEP, art. 129). No âmbito estadual, a própria "
               "AGEPEN adota a mesma sistemática para a remição pela leitura, ao prever o envio mensal ao juízo por ofício (Portaria AGEPEN "
               "15/2021, art. 11). Cabe ao juízo da execução decidir sobre a remição (LEP, art. 66, III, \"c\"), e o tempo remido é computado "
               "como pena cumprida para todos os efeitos (LEP, art. 128).")
    par.append("A ficha do SIAPEN é de abrangência estadual e reúne o histórico do apenado em todas as unidades por onde passou. Por isso, a "
               "direção da unidade atual tem condições de certificar a totalidade dos períodos de trabalho e estudo, sem necessidade de "
               "diligências isoladas em cada estabelecimento.")
    ped, k = [], iter("abcdefgh")
    if ats:
        ped.append("%s) a declaração da remição de %s, referente %s nº %s, computados como pena cumprida (LEP, arts. 126, § 8º, e 128);" % (
            next(k), _dias_txt(total), "ao atestado" if len(ats) == 1 else "aos atestados",
            _lista_e([(a.get("numero") or "s/n").split("/ST")[0] for a in ats])))
    if est:
        ped.append("%s) a declaração da remição pelo estudo indicada acima, com a requisição à unidade da certidão de frequência ou dos "
                   "certificados e relatórios correspondentes, se ainda não juntados (LEP, art. 126, § 1º, I, e § 5º; Res. CNJ 391/2021);" % next(k))
    atual = res.get("unidade_atual_f") or (uns[-1] if uns else "[unidade atual]")
    ped.append("%s) a expedição de ofício à direção da unidade %s para que, no prazo de [10] dias, certifique com base na ficha do SIAPEN todos "
               "os períodos de trabalho e estudo do apenado, inclusive os cumpridos em outras unidades. A certidão deve indicar, para cada "
               "período, a unidade, os dias trabalhados ou as horas de estudo, e o número do atestado correspondente. Os atestados ainda "
               "não encaminhados ao juízo devem ser juntados. Caso a unidade não detenha os atestados dos períodos cumpridos em outro "
               "estabelecimento, requer-se a expedição de ofício à AGEPEN para providenciá-los;" % (next(k), atual))
    ped.append("%s) a certificação, pela Secretaria, de quais desses atestados já constam dos autos sem apreciação;" % next(k))
    ped.append("%s) após a juntada, a declaração das remições faltantes e a remessa dos autos à contadoria para atualização do cálculo de "
               "pena." % next(k))
    out = "DA REMIÇÃO DE PENA E DA DIVERGÊNCIA ENTRE A FICHA DISCIPLINAR (SIAPEN) E O RSPE\n" + "\n\n".join(par) + \
          "\n\nDiante do exposto, requer-se:\n\n" + "\n\n".join(ped)
    prog = rs.to_date(r.get("progressao_previsao_seeu") or "")
    if ats and (not prog or prog > date.today()):
        # a remição conta como pena cumprida: a data da progressão recua os dias remidos (sugestão entre colchetes, a conferir no
        # cálculo); com a data já transcorrida, o reflexo não se aplica e a seção sai
        # (7.14.5) trabalho anterior à data-base: a remição reduz a pena remanescente nessa data, e o lapso cai só a fração sobre ela
        # (1/6 de 84 dias ≈ 14 dias), não os dias inteiros; o trabalho depois da data-base conta inteiro como pena cumprida
        import rspe_remicao as rrm
        db_ = rs.to_date(r.get("data_base_seeu") or "")
        mfr = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", r.get("fracao_progressao_aplicada") or "")
        fr_ = (int(mfr.group(1)) / float(mfr.group(2))) if mfr and int(mfr.group(2)) else None
        antes = 0.0
        if db_:
            for a in ats:
                ini_, fim_ = rs.to_date(a.get("periodo_inicio") or ""), rs.to_date(a.get("periodo_fim") or "")
                v_ = max(a["dias_remidos"], a["dias_trabalhados"] / 3.0) if (todos_trab and a in cheios) else float(a["dias_remidos"])
                if ini_ and fim_ and ini_ <= fim_:
                    n_ = rrm._dias_seg_sab(ini_, fim_)
                    antes += v_ * (rrm._dias_seg_sab(ini_, min(fim_, db_ - timedelta(days=1))) / float(n_ or 1)) if ini_ < db_ else 0.0
                elif not ini_ and _dp(a.get("data") or "") and _dp(a["data"]) < db_:
                    antes += v_  # sem período: emitido antes da data-base, o trabalho é anterior a ela
            antes = min(antes, total)
        if antes > 0.5 and fr_:
            red = (total - antes) + antes * fr_
            nova = ("[data recalculada: por volta de %s - conferir no cálculo]" % rs.fmt(prog - timedelta(days=int(round(red))))) if prog else "[data recalculada]"
            expl_ = (" O trabalho %s é anterior à data-base (%s): a remição reduz a pena remanescente nessa data, sobre a qual incide a fração "
                     "de %s, e o lapso diminui ≈ %s%s." % (
                         "remido" if antes >= total - 0.5 else "de %s desses dias" % _dias_txt(round(antes, 2)), rs.fmt(db_),
                         r.get("fracao_progressao_aplicada").strip(), _dias_txt(round(antes * fr_, 2)),
                         ("; os %s do trabalho posterior a ela contam inteiros" % _dias_txt(round(total - antes, 2))) if total - antes > 0.5 else ""))
        else:
            nova = ("[data recalculada: por volta de %s - conferir no cálculo]" % rs.fmt(prog - timedelta(days=int(total)))) if prog else "[data recalculada]"
            expl_ = (" O trabalho é anterior à data-base (%s): o lapso diminui só a fração sobre os dias remidos - conferir no cálculo." % rs.fmt(db_)
                     if antes > 0.5 else "")
        out += ("\n\nDO REFLEXO NA PROGRESSÃO DE REGIME\nCom a declaração da remição de %s, a data prevista para a progressão de regime "
                "passará de %s para %s, conforme cálculo [anexo].%s" % (_dias_txt(total), rs.fmt(prog) if prog else "[data atual]", nova, expl_))
    return out


def _res_fundamentacao(N, T, f, hoje):
    """Entrada da fundamentação do pedido (fundamentacao_remicao) no modelo da 7.14: só documentos com fato certo - desta execução,
    emitidos ou peticionados depois da última decisão de remição do RSPE e sem ✓ Homologado - e o trabalho registrado depois do
    último atestado (pedir o atestado). Nada vem da diferença de totais."""
    ult = N["R"]["ult_dec"]
    post = N.get("post") or []
    ats = []
    for d in post:
        if not (d["tipo"] == "Atestado de trabalho" or d["tipo"] == "Trabalho (informado por você)") or not d.get("dias"):
            continue
        ps = (d.get("periodo") or "").split(" a ")
        # (7.14.2) remição sem documento com referência dentro do período do atestado: pede-se só a diferença, a conferir na decisão
        ja_ = ("remição de %s, com referência dentro do período do atestado - conferir a decisão antes de requerer" % d["ja_rem_txt"]) if d.get("ja_rem") else ""
        ats.append({"numero": d["num"], "data": rs.fmt(d["emissao"]) if d["emissao"] else "", "dias_trabalhados": d.get("trab") or 0,
                    "dias_remidos": d.get("dias_pedir") or d["dias"], "dias_atestado": d["dias"], "ja_remidos": ja_, "acima_do_possivel": False,
                    "periodo_inicio": ps[0] if len(ps) == 2 else "", "periodo_fim": ps[1] if len(ps) == 2 else ""})
    # estudo registrado depois da última decisão de remição (a parte posterior a ela), sem certidão: estimativa de 4 h por dia letivo
    ate = N["impressao"]
    est_pend, dias_ = [], set()
    for e in f.get("estudos") or []:
        a, b = _dp(e.get("inicio") or ""), _dp(e.get("fim") or "") or ate
        if not a or not b or b < a or (ult and b <= ult) or e.get("horas"):
            continue
        a2 = max(a, ult + timedelta(days=1)) if ult else a
        ds = {x for x in dias_jornada_set(a2, b, "seg-sex") if not em_recesso(x)} - dias_
        if len(ds) >= 3:
            dias_ |= ds
            est_pend.append(dict(e, _ini=a2, _fim=_dp(e.get("fim") or "")))
    horas = len(dias_) * HORAS_DIA_ESTUDO
    exames = [{"exame": d["num"], "data": rs.fmt(d["emissao"])} for d in post if d["tipo"] == "Exame" and d["emissao"]]
    leituras = [{"data": rs.fmt(d["emissao"]), "obras": int(round((d.get("dias") or 0) / 4)), "parcial": False}
                for d in post if d["tipo"] == "Leitura" and d["emissao"]]
    edu = [{"rotulo": d["tipo"] + ((" (%s)" % d["num"]) if d["num"] else ""), "tipo": "certidao" if d["tipo"].startswith("Certidão") else
            "atestado" if d["tipo"] == "Atestado de estudo" else "curso",
            "data": d["emissao"]} for d in post if d["tipo"] in ("Certidão de frequência escolar", "Curso de qualificação", "Atestado de estudo") and d["emissao"]]
    # (7.14.2) trabalho sem atestado: a mesma lista da tela - só os trechos "Pedir atestado" (sem atestado e fora do saldo de remição do
    # RSPE sem documento); o que "pode já estar remido" e o trabalho em curso a acompanhar ficam fora do pedido
    sem_at = []
    for L in T.get("linhas") or []:
        if L["st"] != "sem" or not L.get("pedir_dias"):
            continue
        for a, b in L.get("pedir_trechos") or [(L["pedir_ini"], L["pedir_fim"])]:
            sem_at.append("%s, desde %s, em curso" % (L["local"], rs.fmt(a)) if L.get("em_curso") and (L["fim"] - b).days <= 7
                          else "%s, %s a %s" % (L["local"], rs.fmt(a), rs.fmt(b)))
    return {"atestados_pendentes": ats, "estudo_horas_pend": horas, "estudos_pendentes": est_pend, "exames_f": exames, "leituras_f": leituras,
            "educacao_f": edu, "sem_atestado_f": sem_at, "unidades_f": list(dict.fromkeys(nome_unidade(u) for _d, u in linha_unidades_exibicao(f) if u)),
            # (7.14.5) a unidade atual é a da última entrada (a lista acima é por ordem da primeira passagem: quem volta a uma unidade
            # já visitada ficaria com a anterior)
            "unidade_atual_f": next((n_ for n_ in (nome_unidade(u) for _d, u in reversed(linha_unidades_exibicao(f)) if u)
                                     if n_ and n_ != SEM_UNIDADE), "")}


def _rotulo_doc(d):
    return "%s%s" % (d["tipo"], (" nº " + d["num"]) if d["tipo"].startswith("Atestado") else (" · " + d["num"]) if d.get("num") else "")


def comparativo(r, f, hoje=None, conferidos=None, manuais=None, vinculos=None):
    """Campos da aba Ficha disciplinar (modelo da 7.14): comparação dos totais RSPE x ficha, pontos a conferir, trabalho da ficha x
    atestados, documentos da ficha (✓ Homologado) e remições do RSPE - sem ligar remição a atestado. conferidos: chaves marcadas como
    homologadas; vinculos: {período de trabalho: atestado | "sem"} informados na conferência."""
    import rspe_remicao as rrm
    hoje = hoje or date.today()
    nf = rrm._nf
    out = {"fd_tem": bool(f), "fd_cor": "cinza", "fd_sit": "Sem ficha", "fd_conduta": "", "fd_trab": "", "fd_remidos": "",
           "fd_atestar": "", "fd_estudo": "", "fd_faltas": "", "fd_linhas": [], "fd_dias": None}
    if not f:
        out["fd_linhas"] = [{"emp": "Ficha disciplinar não importada", "per": "", "dias": "", "at": "", "rspe": "", "sit": "Importe o PDF da Ficha Disciplinar (SIAPEN) pelo botão Importar PDFs", "cor": "cinza"}]
        return out
    T = rrm.trabalho_x_atestados(f, hoje, manuais, vinculos, inicio_execucao(r))
    N = rrm.comparacao(r, f, hoje, manuais, conferidos, T)
    if T["inferidos"] and N.get("_sem_doc"):
        # (7.14.4) o saldo de remição sem documento fica com o trabalho mais próximo da remição antes de o atestado sem período emitido
        # depois absorvê-lo pela capacidade: refaz-se a ligação com essas remições reservadas, e a comparação, se ela mudou
        T2 = rrm.trabalho_x_atestados(f, hoje, manuais, vinculos, inicio_execucao(r), reservas=N["_sem_doc"])
        sig = lambda T_: [(L["chave"], L["ini"], L["fim"], L["st"], L["at"]) for L in T_["linhas"]]
        if sig(T2) != sig(T):
            T, N = T2, rrm.comparacao(r, f, hoje, manuais, conferidos, T2)
    N.pop("_sem_doc", None)
    R = N["R"]
    tl_ex = linha_unidades_exibicao(f)
    for L in T["linhas"]:
        L["un"] = _unidade_em(tl_ex, L["ini"])
    # trabalho em curso (coluna "Trabalho atual"): o vínculo aberto da ficha
    em = [x for x in f.get("trabalho") or [] if not x.get("fim") and not x.get("so_lancamento")]
    out["fd_trab"] = ("%s desde %s" % (_nome_emprego(_sem_setores_baixados(em[-1], f.get("eventos") or [])), em[-1]["inicio"])) if em else "sem trabalho em curso"
    out["fd_estuda"] = any(e.get("inicio") and not e.get("fim") for e in f.get("estudos") or [])  # matrícula ativa na ficha
    ult_at = N["ult_at"]
    sem_pos = [L for L in T["linhas"] if L["st"] == "sem" and (L.get("pedir_dias") or not ult_at or L["fim"] > ult_at)]
    out["fd_atestar"] = "Sim" if sem_pos else "Não"
    ult = R["ult_dec"]
    est_post = [d for d in N["post"] if d["tipo"] in ("Certidão de frequência escolar", "Curso de qualificação", "Atestado de estudo", "Leitura", "Exame")]
    est_ap = [x for x in N["est_estim"] if not ult or x["fim"] > ult]
    out["fd_estudo"] = "Sim" if (est_post or est_ap) else "Não"
    out["fd_remidos"] = "%s / %s" % (nf(N["comp"]), nf(R["concedido"]))
    # situação: vermelho só para fato documental certo; diferença a favor da ficha e pontos a conferir, amarelo; nada, verde
    itens, rot = [], []
    if N.get("outra_exec"):
        itens.append({"t": N["outra_exec"], "c": "cinza"})
    if N["vermelho"]:
        rot.append("Atestado sem peticionamento")
    for p_ in N["pontos"]:
        if p_["cor"] == "vermelho":
            itens.append({"t": p_["curto"][0].upper() + p_["curto"][1:], "c": "vermelho"})
    if N["dif"] > rrm.TOL_COMPARACAO:
        rot.append("Verificar remição")
        itens.append({"t": "Verificar remição: ficha %s × RSPE %s" % (nf(N["comp"]), nf(R["concedido"])), "c": "amarelo"})
    elif N["dif"] < -rrm.TOL_COMPARACAO:
        itens.append({"t": "RSPE maior que a ficha (%s × %s)" % (nf(R["concedido"]), nf(N["comp"])), "c": "cinza"})
    elif N["pontos"] or N["comp"] or R["concedido"]:
        itens.append({"t": "Sem diferença (RSPE %s; ficha %s)" % (nf(R["concedido"]), nf(N["comp"])), "c": "verde"})
    conf_ = [p_ for p_ in N["pontos"] if p_["cor"] == "amarelo"]
    for p_ in conf_:
        itens.append({"t": "Ponto a conferir: " + p_["curto"], "c": "amarelo"})
    if N["pedir_dias"]:
        rot.append("Pedir atestado")
        itens.append({"t": "Pedir atestado (≈ %s de remição)" % rs.pl(int(round(N["pedir_dias"])) or 1, "dia", "dias"), "c": "amarelo"})
    if conf_ and not rot:
        rot.append("Conferir pontos")
    cor = "vermelho" if N["vermelho"] else "amarelo" if (N["dif"] > rrm.TOL_COMPARACAO or conf_) else "verde"
    # RSPE maior que a ficha: o que seria amarelo fica cinza (informativo) - salvo o pedido de atestado e o vermelho
    if cor == "verde" and any(p_.get("cor0") for p_ in N["pontos"]):
        rot.append("Conferir (informativo)")
        cor = "cinza"
    elif cor == "verde" and N["dif"] < -rrm.TOL_COMPARACAO and not rot:
        # (7.14.2) RSPE maior que a ficha sem ponto a conferir (ficha sem documentos, p. ex.): informativo, nunca "Em ordem"
        rot.append("RSPE maior que a ficha (%s × %s)" % (nf(R["concedido"]), nf(N["comp"])))
        cor = "cinza"
    # trabalho em curso há até 90 dias, sem atestado: acompanhar (cinza)
    for a_ in N.get("acomp") or []:
        itens.append({"t": "Acompanhar: trabalho em %s em curso desde %s, sem atestado" % (a_["local"], rs.fmt(a_["ini"])), "c": "cinza"})
    if N.get("acomp") and not rot:
        rot.append("Acompanhar atestado")
        cor = "cinza" if cor == "verde" else cor
    sit = " · ".join(rot) or "Em ordem"
    # cabeçalho da linha expandida: só a conclusão (fato vermelho e diferença); os pontos ficam em "Onde pode estar a diferença" e na seção B
    out["fd_sit_itens"] = [i for i in itens if not i["t"].startswith("Ponto a conferir")] if cor != "verde" or N.get("outra_exec") else []
    out["fd_sit_det"] = "; ".join(i["t"] for i in itens if i["c"] not in ("verde", "cinza"))
    faltas = f.get("faltas", [])
    out["fd_faltas"] = ("%d (%s)" % (len(faltas), ", ".join(x["situacao"] for x in faltas))) if faltas else "nenhuma"
    out["fd_remicoes"] = ("Remições no RSPE: " + " · ".join("%s em %s" % (_dias_txt(x["dias"]), rs.fmt(x["decisao"])) for x in R["remicoes"]) +
                          ". O RSPE não diz a origem de cada uma (trabalho, estudo, ENCCEJA/ENEM, leitura).") if R["remicoes"] else "Nenhuma remição no RSPE."
    out["fd_resumo_exec"] = "ficha: %s comprovados (atestados %s · estudo e leitura %s%s) · RSPE: %s concedidos · diferença %s%s" % (
        nf(N["comp"]) + " dias", nf(N["at_desta"]), nf(N["est_comp"] + N["leitura"]), (" · informados por você %s" % nf(N["man"])) if N["n_man"] else "",
        nf(R["concedido"]) + " dias", ("+" if N["dif"] > 0 else "") + nf(N["dif"]), (" · à parte: %s" % rs.pl(len(N["fora"]), "documento", "documentos")) if N["fora"] else "")
    out["fd_fund"] = fundamentacao_remicao(_res_fundamentacao(N, T, f, hoje), r)
    # fatos certos (documentos desta execução posteriores à última decisão, sem ✓): os dias que os decretos e a prioridade consideram,
    # sempre "a conferir nos autos"; ressalva da perda de até 1/3 quando há falta grave depois do período (LEP, art. 127)
    fatos = rrm.fatos_pendentes(N)
    d0 = min([x["doc"]["emissao"] for x in fatos if x["doc"]["emissao"]] or [None], key=lambda d: d or date.max)
    fx = sorted([(_prio_127(r_), d_, r_) for d_, r_ in N["faltas_127"] if d0 and d_ > d0])
    ress = ("salvo perda de até 1/3 dos dias até a falta (LEP, art. 127): %s" % (", ".join(r_ for _p, _d, r_ in fx[:3]) + (" e outras" if len(fx) > 3 else ""))) if fx else ""
    # linhas (exportação da aba, relatório individual): uma por período de trabalho (seção C) e uma por documento com fato ou ponto
    ST = {"auto": ("Vinculado automaticamente", "verde"), "possivel": ("Possível · confirmar", "amarelo"), "provavel": ("Sugerido · confirmar", "amarelo"),
          "sem": ("Sem atestado", "amarelo"), "manual": ("Vinculado por você", "azul")}
    cor_l = lambda L: "cinza" if (N.get("rspe_maior") and ST[L["st"]][1] == "amarelo" and not L.get("pedir_dias")) else ST[L["st"]][1]
    linhas = [{"emp": L["local"] + (" (externo)" if L.get("externo") else ""), "un": L["un"], "per": L["periodo"], "dias": L["dias"], "at": ("nº " + L["at"]) if L["at"] else "—",
               "sit": ST[L["st"]][0] + (" · vínculo sem baixa: conferir" if L.get("conf_dias") and not L.get("pedir_dias") else ""), "cor": cor_l(L)}
              for L in T["linhas"]]
    linhas += [{"emp": _rotulo_doc(d), "un": _unidade_em(tl_ex, _data_local_doc(d, T["linhas"])), "per": d["periodo"] or "—", "dias": "—",
                "at": ("%s remidos" % _fmtn(d["dias"])) if d.get("dias") else "—", "sit": d["sit"], "cor": d["cor"]}
               for d in N["docs"] if d["cor"] in ("vermelho", "amarelo")]
    # modelo da tela (JSON): sem as referências repetidas aos documentos
    docs = [{k: v for k, v in d.items()} for d in N["docs"]]
    for d in docs:
        d["un"] = _unidade_em(tl_ex, _data_local_doc(d, T["linhas"]))
    novo = {k: v for k, v in N.items() if k not in ("docs", "pontos", "post", "vermelho", "faltas_127", "fora")}
    novo.update(docs=docs, pontos=[dict(p_, docs=[d["chave"] for d in p_["docs"]]) for p_ in N["pontos"]], trab=T,
                fora_n=len(N["fora"]), fatos=[{"data": x["data"], "dias": x["dias"], "rotulo": x["rotulo"], "chave": x["doc"]["chave"]} for x in fatos],
                fatos_dias=round(sum(x["dias"] for x in fatos), 2), ressalva_127=ress)
    marc = [d for d in docs if not d["fora"]]
    out.update(fd_cor=cor, fd_sit=sit, fd_conduta=f.get("conduta") or "", fd_linhas=linhas, fd_novo=novo,
               fd_conf_n=sum(1 for d in marc if d["hom"]), fd_conf_tot=len(marc), fd_sem_n=len(sem_pos), fd_sem_pend=int(N["pedir_dias"]))
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


# saída em liberdade ou fuga. A saída por "determinação judicial" e a da prisão domiciliar não são liberdade automática
# (RE_SAIDA_JUDICIAL e saida_judicial): o monitoramento e a domiciliar no curso da execução são cumprimento, e o destino incerto
# fica "a conferir"
RE_SAIDA_LIVRE = _ReFicha(re.compile(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(ALVAR|SOLTURA|LIBERDADE|FUGA|EVAS|LIVRAMENTO|"
                                     r"T[ÉE]RMINO|EXTIN|CUMPRIMENTO DE PENA)|ALVAR[ÁA] DE SOLTURA|\bFUGA\b|EVADIU|EVAS[ÃA]O|FORAGID|N[ÃA]O RETORNOU", re.I))
RE_SAIDA_JUDICIAL = re.compile(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(DETERMINA[ÇC][ÃA]O JUDICIAL|(?:REGIME |PRIS[ÃA]O )?DOMICILIAR)", re.I)


def _saida_fim_custodia(t):
    """Saída que encerra a custódia registrada na unidade para as conferências de detração, prisão e fuga (liberdade, fuga ou
    saída judicial de qualquer destino): o critério de antes da classificação das saídas judiciais."""
    return bool(RE_SAIDA_LIVRE.search(t) or RE_SAIDA_JUDICIAL.search(_sem_fuga_falsa(t)))


def saida_judicial(t, ev=None, x=None):
    """Saída da unidade por "determinação judicial" ou para a prisão domiciliar: None se não é; senão (tipo, destino). Nenhuma é
    liberdade automática. tipo: 'transferencia' (destino em unidade prisional, ou nova entrada em até 3 dias - ev: [(data, texto)]
    da ficha, x: data da saída), 'monitoramento' (UMMVE: cumprimento em monitoramento eletrônico), 'domiciliar' (cumprimento em
    prisão domiciliar), 'apresentacao' (delegacia) ou 'a_conferir' (destino vazio, comarca, vara, "local incerto", sem nova entrada)."""
    u = rs._sem_acento(t or "").upper()
    m = re.search(r"SAIDA DA UNIDADE PENAL.*?MOTIVO:\s*(DETERMINACAO JUDICIAL|(?:REGIME |PRISAO )?DOMICILIAR)", u)
    if not m or RE_SAIDA_LIVRE.search(t):
        return None
    md = re.search(r"DESTINO:\s*([^,]*)", u)
    dest = md.group(1).strip() if md else ""
    if "DOMICILIAR" in m.group(1):
        return "domiciliar", dest
    reg = classificar_unidade(dest)[0] if dest else None
    if reg in ("fechado", "semiaberto", "provisorio", "federal") or (dest and re.search(
            r"\b(?:PDIB|IPCG|EPJFC|PTRAN|CPAIG|PED|EPMR|EPA|PEMRFG\w*|PHAC|UPRB|EPRACA|EP\w*RSA\w*|PSM\w*)\b|UNIDADE PENAL|PENITENC|PRESIDIO|ESTAB\w*\.? PENAL", dest)):
        return "transferencia", dest
    if reg == "monitoramento" or re.search(r"UMMVE|MONITORA", dest):
        return "monitoramento", dest
    if dest and re.search(_DELEGACIA, dest, re.I):
        return "apresentacao", dest
    if ev and x and any(x <= y <= x + timedelta(days=3) and RE_ENTRADA.search(tt) for y, tt in ev):
        return "transferencia", dest
    return "a_conferir", dest


def _rotulo_saida_judicial(x, tipo, dest):
    dd = (" (destino: %s)" % dest.lower()) if dest else " (destino em branco)"
    return {"monitoramento": "saída em %s para o monitoramento eletrônico - cumprimento da pena" % rs.fmt(x),
            "domiciliar": "saída em %s para a prisão domiciliar - cumprimento da pena" % rs.fmt(x),
            "apresentacao": "saída em %s para apresentação na delegacia%s" % (rs.fmt(x), dd),
            "transferencia": "saída em %s por determinação judicial%s, com nova entrada - transferência" % (rs.fmt(x), dd),
            }.get(tipo) or "saída em %s por determinação judicial%s, sem nova entrada em até 3 dias - a conferir se houve soltura" % (rs.fmt(x), dd)
# delegacia de origem: "DP", "1 DP AQUIDAUANA", "1º DP DE JARDIM", ".DP MIRANDA", "1ª DELEGACIA DE POLICIA", "1DP-DOURADOS", "DERF",
# "DEAM", "DPF DOURADOS", "POLINTER", "GARRAS", "DENAR", "CUSTÓDIA/DREX/SR/DPF/MS", "1ª CIA INDEPENDENTE POLICIA MILITAR"
_DELEGACIA = (r"(?:\d{1,2}\s*[ºª°]?\s*)?\.?\s*(?:DP\b|DELEGACIA|DEPAC|CEPOL|CPAC|DERF\b|DEAM\b|DPF\b|POLINTER|GARRAS|DENAR\b|"
              r"CUST[ÓO]DIA/DREX|(?:\d{1,2}\s*[ºª°]?\s*)?CIA\b.{0,30}?POL[ÍI]CIA MILITAR|CIA\s*PM\b|BPM\b)")
RE_ENTRADA_RUA = re.compile(r"(ENTRADA NA UNIDADE PENAL|DEU ENTRADA|\bENTRADA N[OA]\s|\b(?:RE)?INGRESSOU|ADENTROU).*?(PROCEDENTE\s*(?::|D[AOE]S?\b)\s*(?:[^,]{0,40}?[\s-])?" + _DELEGACIA +
                            r"|PROVINDO DA DELEGACIA|AUDI[ÊE]NCIA DE CUST[ÓO]DIA)|ENTRADA NA UNIDADE PENAL:\s*CENTRAL PROVIS[ÓO]RIA DE AUDI[ÊE]NCIA DE CUST[ÓO]DIA", re.I)

# entrada que encerra uma fuga: recaptura e apresentação espontânea ("Procedente: RECAPTURA - INTERIOR", "Procedente: APRESENTACAO
# ESPONTANEA - CAPITAL"). A entrada "Procedente: <cidade> - INTERIOR" ou de outro presídio, sem soltura ou fuga antes, é transferência
RE_ENTRADA_FIM_FUGA = re.compile(r"(ENTRADA NA UNIDADE PENAL|DEU ENTRADA|\bENTRADA N[OA]\s|\b(?:RE)?INGRESSOU).*?PROCEDENTE\s*(?::|D[AOE]S?\b)\s*"
                                 r"(RECAPTURA|APRESENTA[ÇC][ÃA]O ESPONT|APRESENTACAO ESPONT)", re.I)
# prisão em flagrante só narrada, sem entrada formal na unidade ("Nesta data ... foi preso em Flagrante referente aos Autos ..."):
# fato novo a conferir, nunca interrupção automática
RE_FLAGRANTE_NARRADO = re.compile(r"\bFOI PRES[OA] EM FLAGRANTE|\bPRES[OA] EM FLAGRANTE\b", re.I)


def _entrada_fim_fuga(t, ev, x, desde):
    """Entrada por recaptura (encerra a fuga) ou por apresentação espontânea depois de uma fuga registrada na ficha desde 'desde'."""
    m = RE_ENTRADA_FIM_FUGA.search(t or "")
    if not m:
        return False
    if m.group(2).upper().startswith("RECAPTURA"):
        return True
    return any(desde - timedelta(days=30) <= y < x and RE_FUGA_FICHA.search(u) for y, u in ev)


def _flagrante_narrado(t):
    return bool(RE_FLAGRANTE_NARRADO.search(t or "")) and not RE_ENTRADA.search(t or "") and not RE_ENTRADA_RUA.search(t or "")


def custodia_na_ficha(f, ini, datas):
    """Inciso IV (custódia ininterrupta): confronta cada nova prisão que o RSPE registra dentro do período contínuo com a
    movimentação da ficha disciplinar. (True, nota): a ficha mostra a pessoa custodiada antes e depois, sem soltura, fuga
    ou evasão - a prisão ocorreu durante a custódia e não interrompe (o monitoramento eletrônico e a prisão domiciliar no curso da
    execução são custódia); (False, nota): a ficha registra saída em liberdade (alvará, fuga, evasão) ou entrada vinda da
    delegacia/audiência de custódia; (None, nota): a ficha não cobre a data, ou registra saída por determinação judicial de destino
    incerto sem nova entrada, ou prisão em flagrante só narrada (a conferir)."""
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
        # saída por determinação judicial com destino incerto (vazio, comarca, vara, "local incerto") e sem nova entrada em até 3
        # dias, e prisão em flagrante só narrada (sem entrada formal): não são liberdade nem nova prisão automáticas - a conferir.
        # Monitoramento eletrônico e prisão domiciliar no curso da execução são cumprimento e mantêm a custódia
        duv = [_rotulo_saida_judicial(x, *sj) for x, t, sj in ((x, t, saida_judicial(t, ev, x)) for x, t in ev if ini < x <= d and RE_SAIDA_JUDICIAL.search(t))
               if sj and sj[0] == "a_conferir"]
        duv += ["prisão em flagrante só narrada em %s, sem entrada formal na unidade - a conferir se houve nova prisão vinda de fora" % rs.fmt(x)
                for x, t in ev if max(d - timedelta(days=10), ini + timedelta(days=5)) < x <= d + timedelta(days=20) and _flagrante_narrado(t)]
        if duv:
            notas.append("ficha: %s - conferir nos autos se houve interrupção antes da prisão de %s" % ("; ".join(duv), rs.fmt(d)))
            if res is True:
                res = None
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


_RE_SAIDA_TEMP = re.compile(
    r"(?:SAIDA|RETORNO) CONFIRMAD[OA] DO BENEFICIO DE:\s*SAIDA TEMPOR|SAIDA DA UNIDADE PENAL:.*MOTIVO:\s*SAIDA TEMPOR|"
    r"\bSAIU\b.{0,40}\bEM SAIDA TEMPOR|RET(?:ORN|ONR)\w* (?:DE|DA|DO BENEFICIO DE) SAIDA TEMPOR|RETORNO DE SAIDA TEMPOR|"
    r"\bRET(?:ORN|ONR)OU\b[^.;]{0,30}?\b(?:DE|DA|DO)\s+(?:BENEFICIO\s+DE\s+)?SAIDA TEMPOR|"
    r"^SAIDA TEMPORARIA\W.{0,80}\bPERIODO DE\s*\d|\bBENEFICIAD[OA]\b.{0,80}\bSAIDA TEMPOR.*\b(?:RET(?:ORN|ONR)OU\b|RETORNANDO EM .{0,30}SEM ALTERAC)")


def _lancamentos_saida_temporaria(eventos):
    """Lançamentos de saída temporária usufruída: [(data, é retorno)]. Formatos: "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA",
    "Retorno confirmado do benefício ...", "Saída da Unidade Penal ... Motivo: Saída Temporária", "saiu ... em saída temporária",
    "retornou (nesta data) de/da saída temporária" (também entre aspas - 'retornou da "SAÍDA TEMPORÁRIA"' - e com o erro "RETONROU"), "Saída
    Temporária ... no período de d a d" (a saída, pela data inicial do período, e o retorno, pela final, quando já passou na data do
    lançamento) e "beneficiado com saída temporária ..., retornou à esta unidade" / "retornando em d, sem alteração" (o retorno prova
    a saída). A concessão sem registro
    de saída ou retorno ("beneficiado com saída temporária ..., devendo retornar em d") não entra (a decidir)."""
    ds = []
    for e in eventos or []:
        d = _dp(e.get("data") or "")
        u = re.sub(r"\s+", " ", re.sub(r"[\"'´`“”‘’]", "", rs._sem_acento(e.get("texto") or "").upper())).strip()
        if not d or re.match(r"MUDANCA DE CELA", u) or re.search(r"NAO (?:PODE |PODERA )?SAIR|NAO SAIU|NAO USUFRU|NAO LIBERAR|NAO FOI LIBERAD", u):
            continue
        if not _RE_SAIDA_TEMP.search(u):
            continue
        mper = re.match(r"SAIDA TEMPORARIA\W.{0,80}?\bPERIODO DE\s*(\d{2}/\d{2}/\d{2,4})\s*(?:A|ATE|-)\s*(\d{2}/\d{2}/\d{2,4})", u)
        if mper:
            a, b = (rs.to_date(re.sub(r"/(\d{2})$", r"/20\1", x)) for x in mper.groups())
            if a and abs((a - d).days) <= 60:
                ds.append((a, False))
                if b and a <= b <= d:
                    ds.append((b, True))
                continue
        # "retornando em 02/01/2025, sem alteração" lançado depois: o retorno na data dita
        mr = re.search(r"\bRET(?:ORN|ONR)(?:OU|ANDO) (?:A ESTA UNIDADE PENAL NA DATA DE |EM )(\d{2}/\d{2}/\d{4})", u)
        dr = rs.to_date(mr.group(1)) if mr else None
        ds.append((dr if dr and dr <= d and (d - dr).days <= 30 else d, bool(re.search(r"RET(?:ORN|ONR)", u))))
    return ds


def conclusao_certificada(texto):
    """Conclusão do ensino certificada expressamente (art. 9º, XIII, dos Decretos 2024/2025; LEP, art. 126, § 5º - acréscimo de 1/3):
    o registro diz o certificado e a conclusão. A mera petição ("peticionado certificado do ENCCEJA"), a declaração parcial ou a
    aprovação por área não bastam - ficam a verificar."""
    u = rs._sem_acento(texto or "").upper()
    return bool("CERTIFICAD" in u and re.search(r"CONCLUS|CONCLUI", u)
                and not re.search(r"PARCIAL|NA AREA|POR AREA|PETICION|PROTOCOL", u))


def saidas_temporarias_duvidosas(eventos):
    """Lançamentos de saída temporária que não provam a saída usufruída (concessão "beneficiado com saída temporária ..., devendo
    retornar em", "mudança de cela ... motivo: saída temporária", "não pode sair"): [(data, texto)] - não contam, mas, se
    completarem as saídas exigidas, o inciso fica a verificar. A mesma saída já contada (até 10 dias) não entra."""
    contadas = [d for d, _r in _lancamentos_saida_temporaria(eventos)]
    out = []
    for e in eventos or []:
        d = _dp(e.get("data") or "")
        u = re.sub(r"\s+", " ", rs._sem_acento(e.get("texto") or "").upper())
        if not d or not re.search(r"SAIDA TEMPOR", u) or any(abs((d - x).days) <= 10 for x in contadas):
            continue
        if any(abs((d - x).days) <= 10 for x, _t in out):
            continue  # a mesma concessão lançada de novo
        out.append((d, (e.get("texto") or "").strip()[:90]))
    return out


def saidas_temporarias(eventos):
    """Datas das saídas temporárias usufruídas pela ficha (formatos em _lancamentos_saida_temporaria). Saída e retorno da mesma
    saída (até 10 dias) contam uma vez."""
    out = []  # [saída, tem retorno]
    for d, ret in sorted(_lancamentos_saida_temporaria(eventos), key=lambda x: (x[0], x[1])):
        if out and (d - out[-1][0]).days <= 10 and (ret and not out[-1][1] or not ret and (d - out[-1][0]).days <= 1):
            out[-1][1] = out[-1][1] or ret  # a mesma saída: o retorno dela, ou a saída lançada de novo
            continue
        out.append([d, ret])  # só o retorno registrado: conta pela data do retorno (sem supor a da saída)
    return [a for a, _b in out]


def saidas_temporarias_retorno(eventos):
    """Saídas temporárias da ficha com a data do retorno: [(saída ou None, retorno ou None)]. Mesmos formatos de
    saidas_temporarias; o retorno lançado até 10 dias depois da saída fecha a mesma saída."""
    out = []  # [saída, retorno]
    for d, ret in sorted(_lancamentos_saida_temporaria(eventos), key=lambda x: (x[0], x[1])):
        if out and out[-1][0] and not out[-1][1] and (d - out[-1][0]).days <= 10:
            if ret:
                out[-1][1] = d
            continue  # a mesma saída lançada de novo
        out.append([None, d] if ret else [d, None])
    return [tuple(x) for x in out]


def remicao_pendente(comp):
    """Remição possivelmente pendente com fato certo (documentos desta execução, com dias, emitidos ou peticionados depois da última
    decisão de remição do RSPE e sem ✓ Homologado - rspe_remicao.fatos_pendentes): [[fim do período ou emissão dd/mm/aaaa, rótulo,
    dias]], sempre "a conferir nos autos". A diferença de totais e as estimativas (trabalho sem atestado, estudo) ficam de fora."""
    return [[rs.fmt(x["data"]) if isinstance(x["data"], date) else x["data"], x["rotulo"], float(x["dias"])]
            for x in ((comp or {}).get("fd_novo") or {}).get("fatos") or [] if x.get("data") and x.get("dias")]


def remicao_pendente_decretos(r, comp):
    """Grava em r["_rem_pend"] a remição pendente (a aba Indulto e a linha do tempo a usam em todos os decretos, rspe_decretos.avaliar)
    e aplica a regra nos decretos 2022, 2024 e 2025: o indulto ou a comutação que "não atinge" o lapso passa a "A VERIFICAR" quando
    a remição pendente de período até a data do decreto cobre a diferença - a remição é pena cumprida para todos os efeitos,
    inclusive o requisito temporal do indulto (LEP, art. 128; STJ, HC 1.089.923, 11/06/2026). Altera r."""
    r["_rem_pend"] = remicao_pendente(comp)
    if not r["_rem_pend"]:
        return
    refs = {"2022": date(2022, 12, 25), "2024": rs.DECRETOS.get("2024"), "2025": rs.DECRETOS.get("2025")}
    _dias = lambda t: rs.pena_para_dias(t) or 0
    for ano, ref in refs.items():
        if not ref:
            continue
        tot, rots = rs.remicao_pendente_ate(r, ref)
        if tot < 1:
            continue
        for k in ("indulto_%s" % ano, "comutacao_%s" % ano):
            v, det = r.get(k) or "", r.get(k + "_detalhe") or ""
            if not v.startswith("não atinge") or v.startswith("não atinge: pena dos crimes impeditivos") or "posterior à publicação" in v:
                continue
            faltas = []
            if k.startswith("comutacao"):
                for mm in re.finditer(r"✘ Requisito: \S+ da pena cumprida até [\d/]+ = (\d+a\d+m\d+d); cumprido (\d+a\d+m\d+d)", det):
                    faltas.append(_dias(mm.group(1)) - _dias(mm.group(2)))
            else:
                for ln in det.split("\n"):
                    mm = re.match(r"✘ ([IVXL]+): .*?exige (\d+)/(\d+) \(cumprido (\d+a\d+m\d+d) de (\d+a\d+m\d+d)\)", ln)
                    if mm and "não se aplica" not in ln:
                        req = _dias(mm.group(5)) * int(mm.group(2)) // int(mm.group(3))
                        faltas.append(req - _dias(mm.group(4)))
            faltas = [x for x in faltas if x > 0]
            if not faltas or tot < min(faltas):
                continue
            nota = rs.nota_remicao_pendente(tot, rots, ref, min(faltas))
            r[k] = "A VERIFICAR (remição pendente): " + nota
            r[k + "_detalhe"] = det + "\n? Remição pendente: " + nota
            r[k + "_status"] = "verificar"


def complementar_decretos(r, f, hoje=None):
    """Decretos 12.338/2024 e 12.790/2025, art. 9º, XI, XII e XIII: o RSPE não traz saídas temporárias, trabalho externo,
    estudo nem curso concluído; a ficha traz. Resolve pela ficha os incisos que o cálculo deixou "a verificar"
    (a fração e o teto de pena já foram conferidos). Altera r no lugar."""
    if not f:
        return
    hoje = hoje or date.today()
    ev = f.get("eventos", [])
    saidas = saidas_temporarias(ev)
    duv_st = saidas_temporarias_duvidosas(ev)
    externos = [(_dp(t["inicio"]), _dp(t.get("fim") or "")) for t in f.get("trabalho", []) if t.get("externo")]

    def _fim_est(e):
        # matrícula aberta sem registro escolar há mais de um ano: conta só até o último registro (não "até hoje")
        if _dp(e.get("fim") or ""):
            return _dp(e["fim"])
        ult = max([x for x in (_dp(e.get("inicio") or ""), _dp(e.get("ult_registro_edu") or "")) if x] or [hoje])
        return ult if (hoje - ult).days > 365 else hoje
    estudos = [(_dp(e["inicio"]), _fim_est(e), e) for e in f.get("estudos", []) if _dp(e.get("inicio") or "")]
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
        # autorização/termo de compromisso de trabalho externo nos 3 anos anteriores, sem a prestação registrada: a conferir
        aut = [x for x in f.get("externo_a_conferir") or [] if ref - timedelta(days=3 * 365) <= (_dp(x.get("inicio") or "") or date.min) <= ref]
        if ns >= 5:
            res["XI"] = (True, "ficha: %d saídas temporárias até %s (última em %s)" % (ns, rs.fmt(ref), rs.fmt(max(d for d in saidas if d <= ref))))
        elif dext >= 360:
            res["XI"] = (True, "ficha: %s de trabalho externo nos 3 anos anteriores" % rs.pl(dext, "dia", "dias"))
        elif ns + len([d for d, _t in duv_st if d <= ref]) >= 5:
            # só contam as saídas usufruídas (registro de saída ou retorno); a concessão sem esse registro, que completaria as 5,
            # fica a verificar - não se descarta nem se conta
            _dv = [(d, t) for d, t in duv_st if d <= ref]
            res["XI"] = (None, "ficha: %s usufruídas até %s e %s sem registro de saída ou retorno (%s) - conferir se foram usufruídas" % (
                rs.pl(ns, "saída temporária", "saídas temporárias"), rs.fmt(ref), rs.pl(len(_dv), "lançamento", "lançamentos"),
                "; ".join("%s: %s" % (rs.fmt(d), t) for d, t in _dv[:3]) + ("; ..." if len(_dv) > 3 else "")))
        elif aut:
            res["XI"] = (None, "ficha: %s até %s e %s de trabalho externo registrado nos 3 anos anteriores; autorização ou termo de compromisso "
                               "de trabalho externo em %s, sem registro da prestação - conferir se trabalhou 12 meses" % (
                                   rs.pl(ns, "saída temporária", "saídas temporárias"), rs.fmt(ref), rs.pl(dext, "dia", "dias"),
                                   ", ".join(_br(x["inicio"]) for x in aut[:3])))
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
            # pelo texto do registro do mesmo dia (a regra atual vale também para a ficha gravada antes: a marca gravada era mais larga)
            us = [e["texto"].upper() for e in ev if e.get("data") == x["data"] and x["exame"].split()[0] in (e.get("texto") or "").upper()]
            if not us:
                return bool(x.get("certificado"))
            return x["exame"].startswith("ENCCEJA") and any(conclusao_certificada(u) for u in us)
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
        # o que não é inciso do art. 9º entra na conclusão como na análise do RSPE: "✔ Art. 10, III, c" (mulheres) e os "?" do
        # art. 10, do § 2º, II a VI (metade do lapso) e do XIV/XV com VGA em branco. Sem eles, a ficha que nega o XII/XIII (linhas
        # que só aparecem com mais tempo cumprido) dava "não atinge" a quem seguia "a verificar" pelo art. 10 ou pelo § 2º
        poss_art = [m.group(1).replace("Art.", "art.") for m in re.finditer(r"^✔ (Art\. \d+[^:]*):", det, re.M)]
        for m in re.finditer(r"^\? (.+)$", det, re.M):
            t = m.group(1)
            x = ("XIV, XV (VGA em branco)" if t.startswith("XIV/XV") else "§ 2º, II a VI (metade do lapso)" if t.startswith("§ 2º")
                 else "art. 10 (mulheres)" if t.startswith("Art. 10") else "")
            if x and x not in verif:
                verif.append(x)
        antes = r.get(k) or ""
        # NÃO CABE (art. 6º, falta grave nos 12 meses): a ficha não reabre - a falta afasta o indulto qualquer que seja o inciso
        # "A VERIFICAR: ... | antes: ..." (pena extinta depois do decreto) e tempo cumprido incerto: a dúvida não é de inciso - a
        # ficha não a resolve, e o resultado não volta a "POSSÍVEL"
        if (antes.startswith(("CONCEDIDO", "INDEFERIDO", "não se aplica", "VEDAD", "excluído", "NÃO CABE", "A VERIFICAR: tempo cumprido incerto"))
                or " | antes: " in antes or r.get(k + "_status") in ("vedado",)):
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
        # o inciso XV não depende do tempo cumprido nem da pena: a ressalva sobre eles não o alcança (como na análise do RSPE)
        ressalva_xv = "; ".join(x for x in ressalva.split("; ") if x and not x.startswith(("conferir o tempo cumprido", "conferir a pena considerada")))
        if poss and ressalva and "XV" in poss and not ressalva_xv:
            outros = [p for p in poss if p != "XV"] + poss_art + verif
            r[k] = "POSSÍVEL%s: art. 9º, XV%s" % (rot, aviso)
            r[k + "_status"] = rs.status_texto_decreto(r[k])
            if (r.get(kc) or "").startswith("POSSÍVEL"):
                r[kc] = "prejudicada: indulto cabível (art. 13, § 5º)"
            concl = "possível pelo art. 9º, XV%s." % ((" (a verificar: %s - %s)" % (", ".join(dict.fromkeys(outros)), ressalva)) if outros else "")
        elif (poss or poss_art) and ressalva:
            # a ficha confirma o requisito, mas a ressalva continua: segue "a verificar"
            r[k] = "A VERIFICAR%s: art. 9º, %s%s" % (rot, ", ".join(dict.fromkeys(poss + poss_art + verif)), aviso)
            r[k + "_status"] = "verificar"
            concl = "a verificar (%s) - %s." % (", ".join(dict.fromkeys(poss + poss_art + verif)), ressalva)
        elif poss or poss_art:
            # como na análise do RSPE: "art. 9º, I, XII; art. 10, III, c"
            _inc = "; ".join(filter(None, [("art. 9º, " + ", ".join(poss)) if poss else "", ", ".join(poss_art)]))
            r[k] = "POSSÍVEL%s: %s%s" % (rot, _inc, aviso)
            r[k + "_status"] = rs.status_texto_decreto(r[k])  # falta do art. 6º a verificar no aviso: a verificar (critério único)
            if (r.get(kc) or "").startswith("POSSÍVEL"):
                r[kc] = "prejudicada: indulto cabível (art. 13, § 5º)"
            concl = "possível pelo %s (conferido na ficha disciplinar)." % _inc
        elif verif:
            r[k] = "A VERIFICAR%s: art. 9º, %s%s" % (rot, ", ".join(verif), aviso)
            r[k + "_status"] = "verificar"
            concl = "a verificar (%s)." % ", ".join(verif)
        else:
            r[k] = "não atinge: incisos conferidos na ficha disciplinar não atendidos" + aviso
            r[k + "_status"] = "nao"
            concl = "não atinge nenhum inciso nesta data (%s conferidos na ficha disciplinar)." % ", ".join(k2 for k2 in ("IV", "XI", "XII", "XIII") if k2 in res)
        r[k + "_explica"] = re.sub(r"^Conclusão: .*$", "Conclusão: " + concl, exp, flags=re.M) if exp else exp
