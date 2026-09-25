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
        return date(int(txt[6:10]), int(txt[3:5]), int(txt[0:2]))
    except Exception:
        return None


def _num(txt):
    """Número da ficha ('4,33', '4.33...', '12'): só a parte numérica; 0 se não houver."""
    m = re.search(r"\d+(?:[.,]\d+)?", str(txt or ""))
    return float(m.group(0).replace(",", ".")) if m else 0.0


def texto_pdf(caminho):
    with pdfplumber.open(caminho) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def e_ficha(texto):
    return "FICHA DISCIPLINAR" in texto.upper() and "SIAPEN" in texto.upper()


def _limpar(t):
    # remove cabeçalhos/rodapés repetidos do SIAPEN
    out = []
    for l in t.splitlines():
        u = l.strip()
        if not u:
            continue
        if re.search(r"Confidencial ::|Responsável:|Projeto SIAPEN|^RUA:|^CEP:|^FONE:|^\d{2}:\d{2}:\d{2}$|^RRMB|^\d{2}:\d{2}: ", u):
            continue
        out.append(u)
    return "\n".join(out)


MESES = {"JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "MARCO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7, "AGOSTO": 8,
         "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12}


def _estudos(eventos):
    """Períodos de estudo da ficha (LEP, art. 126, § 1º, I): matrícula -> cancelamento/encerramento, por série/curso.
    Cursos em texto livre (ex.: "CURSO DE BARBEIRO/SENAC 40H ... 09 DE AGOSTO 2021 A 20 DE AGOSTO 2021") viram um período
    com a carga horária declarada."""
    out, abertos = [], []

    def fechar(p, data, motivo):
        p["fim"], p["motivo_fim"] = data, motivo
        abertos.remove(p)

    for e in eventos:
        u = e["texto"].upper()
        if "EDUCA" not in u and "CURSO" not in u:
            continue
        if "TRABALHO" in u and "CURSO" not in u:
            continue
        m = re.search(r"MATR[ÍI]CULOU-SE NA S[ÉE]RIE:\s*(.+?)\s+TURMA:\s*(.*?)\s*PER[ÍI]ODO:\s*(.*)$", u)
        if m:
            serie = m.group(1).strip(" .-")
            for p in [p for p in abertos if p["curso"] == serie]:
                fechar(p, e["data"], "nova matrícula na mesma série")
            p = {"curso": serie, "turma": m.group(2).strip(" .") , "turno": m.group(3).strip(" ."), "inicio": e["data"], "fim": "", "motivo_fim": "", "horas": None}
            abertos.append(p); out.append(p)
            continue
        m = re.search(r"MATR[ÍI]CULA CANCELADA\.?\s*S[ÉE]RIE:\s*(.+?)\s+PER[ÍI]ODO", u)
        if m:
            serie = m.group(1).strip(" .-")
            alvo = [p for p in abertos if p["curso"] == serie] or abertos[-1:]
            for p in alvo:
                fechar(p, e["data"], "matrícula cancelada")
            continue
        if re.search(r"CANCELAMENTO DE MATR[ÍI]CULA|CONCLU[ÍI]U|CONCLUS[ÃA]O DO CURSO", u):
            for p in list(abertos):
                fechar(p, e["data"], "concluído" if "CONCLU" in u else "matrícula cancelada" + (" (saída da unidade)" if "SA" in u and "PRES" in u else ""))
            continue
        if "CURSO" in u:
            h = re.search(r"(\d+)\s*(?:H\b|HORAS)", u)
            per = re.search(r"(\d{1,2})\s+DE\s+([A-ZÇ]+)\s+(?:DE\s+)?(\d{4})\s+(?:A|À|ATÉ)\s+(\d{1,2})\s+DE\s+([A-ZÇ]+)\s+(?:DE\s+)?(\d{4})", u)
            ini, fim = e["data"], ""
            if per and per.group(2) in MESES and per.group(5) in MESES:
                ini2 = "%02d.%02d.%s" % (int(per.group(1)), MESES[per.group(2)], per.group(3))
                fim2 = "%02d.%02d.%s" % (int(per.group(4)), MESES[per.group(5)], per.group(6))
                if _dp(ini2) and _dp(fim2):  # data impossível (ex.: 31 de junho): fica a data do registro
                    ini, fim = ini2, fim2
            nome = (re.search(r"CURSO (?:DE )?([A-ZÇÃÕÁÉÍÓÚ/ ]+?)(?:\s+\d|,|\.|$)", u) or [None, "curso"])[1].strip()
            chave = re.sub(r"\W", "", nome)[:5]
            # o mesmo curso citado de novo (ex.: início remarcado) substitui o registro anterior
            ant = [p for p in out if p.get("livre") and re.sub(r"\W", "", p["curso"])[:5] == chave]
            for p in ant:
                out.remove(p)
                if p in abertos:
                    abertos.remove(p)
            out.append({"curso": nome, "turma": "", "turno": "", "inicio": ini, "fim": fim, "motivo_fim": "período do curso" if fim else "",
                        "horas": int(h.group(1)) if h else None, "livre": True})
    return out


def extrair(caminho):
    t = texto_pdf(caminho)
    if not e_ficha(t):
        raise ValueError("não é uma Ficha Disciplinar do SIAPEN")
    t = _limpar(t)
    f = {"arquivo": caminho, "tipo": "ficha_disciplinar"}
    cab = t.split("HISTÓRICO")[0]
    f["nome"] = (re.search(r"Nome:\s*(.+?)\s+RGI:", cab) or [None, ""])[1].strip() if re.search(r"Nome:\s*(.+?)\s+RGI:", cab) else ""
    f["rgi"] = (re.search(r"RGI:\s*(\d+)", cab) or [None, ""])[1]
    f["cpf"] = (re.search(r"CPF:\s*([\d.\-]+\d)", cab) or [None, ""])[1]
    f["data_nascimento"] = (re.search(r"Data Nascimento:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    f["artigo"] = (re.search(r"Artigo:\s*(.+)", cab) or [None, ""])[1].strip()
    f["data_prisao"] = (re.search(r"Data Prisão:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    f["condenacao"] = (re.search(r"Condenação:\s*(.+)", cab) or [None, ""])[1].strip()
    f["unidade"] = (re.search(r"Unidade Penal:\s*(.+)", cab) or [None, ""])[1].strip()
    f["data_entrada"] = (re.search(r"Data Entrada:\s*(\d{2}/\d{2}/\d{4})", cab) or [None, ""])[1]
    mc = re.search(r"HIST[ÓO]RICO\s*-\s*CONDUTA:\s*([^\n]+)", t) or re.search(r"CONDUTA:\s*([A-ZÇÃÕÁÉÍÓÚÂÊÔ/ ]+)", t)
    f["conduta"] = (mc.group(1).strip() if mc else "")
    f["data_impressao"] = (re.search(r"Impresso em (\d{2}/\d{2}/\d{4})", texto_pdf(caminho)) or [None, ""])[1]
    autos = sorted(set(re.findall(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", t)))
    f["autos"] = autos

    # ---- eventos do histórico ----
    hist = t.split("HISTÓRICO", 1)[1] if "HISTÓRICO" in t else t
    partes = RE_LINHA.split(hist)
    eventos = []
    for i in range(1, len(partes) - 1, 2):
        d, txt = partes[i], " ".join(partes[i + 1].split())
        eventos.append({"data": d, "d": _dp(d), "texto": txt})
    f["eventos"] = [{"data": e["data"], "texto": e["texto"]} for e in eventos]

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
    f["trabalho"] = trabalho
    f["baixas_sem_inicio"] = baixas_orfas

    # ---- atestados de trabalho (dias trabalhados / remidos) ----
    atest = []
    for e in eventos:
        u = e["texto"].upper()
        if "ATESTADO DE TRABALHO" not in u:
            continue
        # números por extenso entre parênteses ("157 (CENTO E CINQUENTA E SETE) DIAS") atrapalham a leitura
        u = re.sub(r"\(\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ ]+\s*\)", " ", u)
        u = re.sub(r"\s+", " ", u)
        m = re.search(r"(\d+)\s*DIAS TRABALHADOS\s*E\s*([\d.,]+)\s*(?:DIAS\s*)?REMIDOS", u)
        if not m:
            continue
        n = re.search(r"ATESTADO DE TRABALHO(?:\s+PRISIONAL)?(?:\s+[A-Z]{2,8})?\W{0,3}\s*N\s*[.ºO°]*\s*([\w./-]+?)[,.;]?(?:\s|$)", u)
        _AT = r"\s*(?:À|Á|A|ATÉ|-)\s*"
        per = re.search(r"(?:PER[IÍ]ODO(?: TRABALHADO)?\s*(?:DE|NA EMPRESA[^\d]*)?)\s*(\d{2}/\d{2}/\d{2,4})\s*(?:A|-)?\s*(\d{2}/\d{2}/\d{2,4})", u)
        if not per:
            per = re.search(r"(\d{2}/\d{2}/\d{2,4})\s+(?:A\s+)?(\d{2}/\d{2}/\d{2,4})", u)
        emp = re.search(r"NA EMPRESA[,:]?\s*(.+?)\s+(?:\(|DE\s+\d|\d{2}/\d{2})", u) or re.search(r"FUN[ÇC][ÃA]O\s+([^(]+?)\s*\(", u)
        # trechos "NA/NO <setor> DE dd/mm/aa À dd/mm/aa" (um atestado pode cobrir vários empregos)
        trechos = [{"setor": t.group(1).strip(" ,.-"), "inicio": t.group(2), "fim": t.group(3)}
                   for t in re.finditer(r"\bNO SETOR DE\s+([^,;]+?),?\s*(?:NO\s+)?PER[IÍ]ODO DE\s*(\d{2}/\d{2}/\d{2,4})" + _AT + r"(\d{2}/\d{2}/\d{2,4})", u)]
        if not trechos:
            trechos = [{"setor": t.group(1).strip(" ,.-"), "inicio": t.group(2), "fim": t.group(3)}
                       for t in re.finditer(r"\b(?:NA|NO|NAS|NOS)\s+(?:EMPRESA\s+)?([^,;]+?)\s+(?:DE\s+)?(\d{2}/\d{2}/\d{2,4})" + _AT + r"(\d{2}/\d{2}/\d{2,4})", u)
                       if not re.match(r"PER[IÍ]ODO", t.group(1).strip())]
        if not per and not trechos:
            per = re.search(r"(\d{2}/\d{2}/\d{2,4})" + _AT + r"(\d{2}/\d{2}/\d{2,4})", u)
        pi, pf = (per.group(1), per.group(2)) if per else ("", "")
        if trechos and not per:
            pi = min(trechos, key=lambda t: _d(t["inicio"]) or date.max)["inicio"]
            pf = max(trechos, key=lambda t: _d(t["fim"]) or date.min)["fim"]
        atest.append({
            "data": e["data"], "numero": n.group(1) if n else "",
            "dias_trabalhados": int(m.group(1)), "dias_remidos": _num(m.group(2)),
            "periodo_inicio": pi, "periodo_fim": pf,
            "empresa": emp.group(1).strip(" ,-") if emp else "",
            "autos": (re.search(r"AUTOS N[ºO°]?\s*([\d.-]+)", u) or [None, ""])[1],
            "trechos": trechos,
        })
    f["atestados"] = atest
    # ENCCEJA / ENEM: certificado peticionado ou registrado na ficha (remição por aprovação - Res. CNJ 391/2021; LEP, art. 126,
    # e § 5º, +1/3, quando houver conclusão do ensino certificada)
    exames = []
    for e in eventos:
        u = e["texto"].upper()
        mx = re.search(r"\b(ENCCEJA|ENEM)\b\s*(\d{4})?", u)
        if mx and re.search(r"CERTIFICAD|APROVA|PETICION|DECLARA", u):
            exames.append({"exame": mx.group(1) + ((" " + mx.group(2)) if mx.group(2) else ""), "data": e["data"]})
    f["exames"] = exames
    f["dias_trabalhados_atestados"] = sum(a["dias_trabalhados"] for a in atest)
    f["dias_remidos_atestados"] = round(sum(a["dias_remidos"] for a in atest), 2)

    # ---- faltas disciplinares ----
    faltas = []
    for e in eventos:
        u = e["texto"].upper()
        if "CONSELHO DISCIPLINAR" not in u and "FALTA DISCIPLINAR" not in u and "FALTA GRAVE" not in u:
            continue
        if re.search(r"REGISTRO DE FALTA|LAN[ÇC]AMENTO DE FALTA|FALTA GRAVE", u) and "ARQUIV" not in u and "INSTAURA" not in u and "ISOLADO" not in u:
            art = re.search(r"INFRING\w*\s*(?:EM TESE)?\s*O?\s*ART\.?\s*(\d+)[, ]*\s*(?:INCISO|INC\.?)?\s*([IVXL]+)?", u) or re.search(r"ART\.?\s*(\d+)[, ]*\s*(?:INCISO|INC\.?)?\s*([IVXL]+)?", u)
            cometida = re.search(r"COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", u)
            faltas.append({"data_registro": e["data"], "data_fato": cometida.group(1) if cometida else e["data"],
                           "artigo": ("art. %s%s da LEP" % (art.group(1), (", " + art.group(2)) if art.group(2) else "")) if art else "",
                           "grave": bool(art and art.group(1) in ("50", "52")) or "FALTA GRAVE" in u,
                           "texto": e["texto"], "situacao": "registrada", "padic": "", "resultado": ""})
    for e in eventos:
        u = e["texto"].upper()
        m = re.search(r"OCORRIDO EM\s*(\d{2}/\d{2}/\d{4})|COMETIDA EM\s*(\d{2}/\d{2}/\d{4})", u)
        alvo = None
        if m:
            dt = m.group(1) or m.group(2)
            alvo = next((x for x in faltas if x["data_fato"] == dt), None)
        if alvo is None and faltas and ("PADIC" in u or "ARQUIV" in u or "HOMOLOG" in u):
            alvo = min(faltas, key=lambda x: abs((_dp(e["data"]) - _dp(x["data_registro"])).days) if _dp(e["data"]) and _dp(x["data_registro"]) else 9999)
        if not alvo:
            continue
        mp = re.search(r"PADIC\s*/?\s*\w*\s*N[ºO°]?\s*([\d./-]+)", u)
        if "INSTAURA" in u:
            alvo["situacao"] = "PADIC instaurado"
            if mp:
                alvo["padic"] = mp.group(1)
        if "ARQUIV" in u:
            alvo["situacao"] = "arquivada"
            alvo["resultado"] = e["texto"]
            alvo["data_resultado"] = e["data"]
        elif re.search(r"HOMOLOG|RECONHEC|PUNI[ÇC][ÃA]O|SAN[ÇC][ÃA]O", u):
            alvo["situacao"] = "homologada/punida"
            alvo["resultado"] = e["texto"]
            alvo["data_resultado"] = e["data"]
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

def confrontar(r, f, hoje=None):
    """Compara ficha (f) com o registro do RSPE (r). Devolve lista de itens no formato da auditoria:
    {nivel, titulo, detalhe, fundamento}."""
    hoje = hoje or date.today()
    itens = []
    if not f:
        return itens
    linhas, res = quadro_trabalho(r, f, hoje)
    ats = f.get("atestados", [])
    # 1) atestado sem nenhuma remição lançada no RSPE depois dele: certo que não foi homologado
    for a in res["atestados_pendentes"]:
        per = (" - %s a %s" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else ""
        itens.append({"nivel": "alerta",
                      "titulo": "Remição a requerer: atestado nº %s (%s), %s remidos" % ((a.get("numero") or "s/n").split("/ST")[0], a["data"], _dias_txt(a["dias_remidos"])),
                      "detalhe": "Atestado de %s trabalhados%s e nenhuma remição lançada no RSPE depois dele. Requerer a remição." % (_dias_txt(a["dias_trabalhados"]), per),
                      "fundamento": "LEP, arts. 126 (1 dia a cada 3 trabalhados) e 126, § 8º; Súmula 562 STJ."})
    if not res["atestados_pendentes"] and res["diferenca"] >= 1:
        itens.append({"nivel": "verificar",
                      "titulo": "Remição a conferir: ficha ≈ %s × RSPE %s" % (_dias_txt(res["remidos_execucao"] + res["remidos_estudo"]), _dias_txt(res["homologados"])),
                      "detalhe": "Os atestados e o estudo desta execução somam mais que as remições do RSPE. O RSPE não indica a origem de cada remição "
                                 "(trabalho, estudo, ENCCEJA/ENEM, leitura), então a diferença real pode ser maior: conferir nas decisões de remição.",
                      "fundamento": "LEP, art. 126."})
    # 2) proporção 1/3 nos atestados
    for a in ats:
        esperado = a["dias_trabalhados"] / 3.0
        if a["dias_trabalhados"] and abs(esperado - a["dias_remidos"]) > 1:
            itens.append({"nivel": "verificar", "titulo": "Atestado %s: %s trabalhados dariam %s remidos, consta %s" % (a.get("numero") or a["data"], _dias_txt(a["dias_trabalhados"]), _fmtn(esperado), _fmtn(a["dias_remidos"])),
                          "detalhe": "Proporção legal: 1 dia de pena a cada 3 dias de trabalho.", "fundamento": "LEP, art. 126, § 1º, II."})
    # 3) trabalho sem atestado e baixas sem início registrado: um item cada, com a lista
    sem = [L for L in linhas if L["cor"] == "amarelo" and L["at"].startswith("sem atestado")]
    if sem:
        tot = sum(int(re.match(r"\d+", L["dias"]).group()) for L in sem if re.match(r"\d+", L["dias"]))
        itens.append({"nivel": "verificar", "titulo": "Trabalho sem atestado: %s, ≈ %s (≈ %d remidos)" % (rs.pl(len(sem), "período", "períodos"), rs.pl(tot, "dia", "dias"), tot // 3),
                      "detalhe": "; ".join("%s%s, %s (%s)" % (L["emp"], (" - " + L["un"]) if L.get("un") and L["un"] != "—" else "", _br(L["per"]), L["dias"]) for L in sem) +
                                 ". Estimativa em dias corridos; a unidade atesta só os dias efetivamente trabalhados. Requerer os atestados e a remição.",
                      "fundamento": "LEP, arts. 126 e 129."})
    bx = [L for L in linhas if L["per"].startswith("início não registrado")]
    if bx:
        itens.append({"nivel": "verificar", "titulo": "Baixa de trabalho sem início registrado: %s" % "; ".join(
                          "%s%s em %s" % (L["emp"], (" (" + L["un"] + ")") if L.get("un") and L["un"] != "—" else "", (re.search(r"baixa em (\S+)", L["per"]) or [None, "?"])[1]) for L in bx),
                      "detalhe": "A ficha registra a saída do trabalho, mas não quando ele começou (%s). A unidade o mantinha alocado sem registro de entrada: requerer à unidade o período trabalhado, o atestado e a remição." % "; ".join(
                          (re.search(r"\((último registro.+)\)", L["per"]) or [None, "sem registro anterior"])[1] for L in bx),
                      "fundamento": "LEP, arts. 126 e 129."})
    # 3b) falta grave anterior registrada na ficha x perda de dias remidos no RSPE (art. 127: sem desconto em duplicidade)
    itens.extend(_falta_anterior_x_perda(r, f))
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
    n, d = 0, a
    while d <= b:
        if d.weekday() < 5:
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
        elif ((e["_fim"] or hoje) - (e["_ini"] or hoje)).days + 1 < 3:  # período inclusivo: 01 a 03 = 3 dias
            e["_status"] = "curto"  # a lei exige as 12 h divididas em pelo menos 3 dias
        elif not e["_rem_depois"]:
            e["_status"] = "sem_remicao"
        else:
            e["_status"] = "conferir"
    return ats, incs, ini, ests


def _cobertura(t, ats):
    """Atestados que cobrem o período de trabalho t (por período, trecho ou nome da empresa)."""
    ti, tf = _dp(t.get("inicio") or ""), _dp(t.get("fim") or "")
    nome = _norm(_nome_emprego(t)) or _norm(t.get("setor"))
    out = []
    for a in ats:
        if a.get("trechos"):
            for tr in a["trechos"]:
                i2, f2 = _d(tr["inicio"]), _d(tr["fim"])
                if i2 and f2 and ti and i2 <= (tf or date.max) and f2 >= ti and (_norm(tr["setor"])[:6] in nome or nome[:6] in _norm(tr["setor"])):
                    out.append((a, i2, f2)); break
        elif a.get("periodo_inicio"):
            i2, f2 = _d(a["periodo_inicio"]), _d(a["periodo_fim"])
            if i2 and f2 and ti and i2 <= (tf or date.max) and f2 >= ti:
                out.append((a, i2, f2))
    return out


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


def quadro_trabalho(r, f, hoje=None):
    """Uma linha por emprego da ficha: período, atestado que o cobre, remição no RSPE e providência.
    Devolve (linhas, resumo)."""
    hoje = hoje or date.today()
    ats, incs, ini_exec, ests = vincular(r, f, hoje)
    trab = [t for t in f.get("trabalho", []) if _dp(t.get("inicio") or "")]
    cob = {id(t): _cobertura(t, ats) for t in trab}
    usados = {id(a) for c in cob.values() for a, _, _ in c}
    # atestados sem período: cobrem os empregos encerrados até a data do atestado ainda sem atestado (do mais recente para trás)
    for a in ats:
        if id(a) in usados or a.get("periodo_inicio"):
            continue
        da = _dp(a["data"])
        cand = sorted([t for t in trab if not cob[id(t)] and _dp(t.get("fim") or "") and _dp(t["fim"]) <= da + timedelta(days=5)],
                      key=lambda t: _dp(t["fim"]), reverse=True)
        acum = 0
        for t in cand:
            if acum >= a["dias_trabalhados"]:
                break
            cob[id(t)] = [(a, _dp(t["inicio"]), _dp(t["fim"]))]
            acum += (_dp(t["fim"]) - _dp(t["inicio"])).days + 1
            usados.add(id(a))
    ult_at = max((a["_fim"] for a in ats if a.get("_fim")), default=None)
    linhas = []
    # blocos para a tela: um por atestado (com os trechos de emprego que ele cobre) e os períodos sem atestado
    blocos_at, sem_itens = {}, []

    def _seg(a, emp, s0, e0):
        b = blocos_at.setdefault(id(a), {"a": a, "itens": []})
        b["itens"].append({"emp": emp, "_a": s0, "_b": e0})

    def at_txt(a):
        return "nº %s · %s remidos" % ((a.get("numero") or "s/n").split("/ST")[0], _fmtn(a["dias_remidos"]))

    def at_full(a):
        return "Atestado nº %s de %s: %s trabalhados, %s remidos%s" % ((a.get("numero") or "s/n").split("/ST")[0], _br(a["data"]), _dias_txt(a["dias_trabalhados"]), _fmtn(a["dias_remidos"]),
                                                                          (" (%s a %s)" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else "")

    for t in trab:
        ti, tf = _dp(t["inicio"]), _dp(t.get("fim") or "")
        dias = ((tf or hoje) - ti).days + 1
        per = "%s a %s" % (t["inicio"], t["fim"]) if tf else "%s em diante (em curso)" % t["inicio"]
        c = cob[id(t)]
        fora = ini_exec and (tf or hoje) < ini_exec
        L = {"emp": _nome_emprego(t) + (" (externo)" if t.get("externo") else ""), "per": per, "dias": dias, "_ini": ti}
        if c and not fora:
            for x, i2, f2 in c:
                s0 = max(ti, i2) if i2 else ti
                e0 = min(tf or hoje, f2) if f2 else (tf or hoje)
                _seg(x, L["emp"], s0, e0)
        if c:
            xs = [x for x, _, _ in c]
            L["at"] = "; ".join(at_txt(x) for x in xs)
            L["at_full"] = "; ".join(at_full(x) for x in xs)
            pend = [x for x in xs if x["_status"] == "sem_remicao"]
            if pend:
                L["sit"] = "Requerer remição (%s)" % _dias_txt(sum(x["dias_remidos"] for x in pend))
                L["sit_full"] = "Nenhuma remição lançada no RSPE depois do atestado: não foi homologado."
                L["cor"] = "vermelho"
            elif all(x["_status"] == "anterior" for x in xs):
                L["sit"], L["cor"] = "Anterior a esta execução", "cinza"
            else:
                L["sit"], L["cor"] = "Conferir homologação", "cinza"
                L["sit_full"] = "O RSPE tem remições posteriores ao atestado, mas não indica a origem de cada uma: conferir na decisão."
            # trabalho que continuou depois do fim do período atestado
            fim_cob = max(f2 for _, _, f2 in c)
            resto_fim = tf or hoje
            if (resto_fim - fim_cob).days >= 15 and not fora:
                nd = (resto_fim - fim_cob).days
                L["per"] = "%s a %s" % (t["inicio"], rs.fmt(fim_cob))
                L["dias"] = (fim_cob - ti).days + 1
                L2 = {"emp": L["emp"], "per": "%s a %s" % (rs.fmt(fim_cob + timedelta(days=1)), rs.fmt(tf) if tf else "hoje (em curso)"), "dias": nd, "_ini": fim_cob + timedelta(days=1),
                      "at": "sem atestado", "at_full": "Trabalho posterior ao último atestado da ficha.", "sit": "Pedir atestado", "cor": "amarelo"}
                sem_itens.append({"emp": L["emp"], "_a": fim_cob + timedelta(days=1), "_b": tf or hoje, "per": L2["per"], "sit": "Pedir atestado"})
                linhas.append(L)
                linhas.append(L2)
                continue
        else:
            L["at"] = "—"
            if fora:
                L["sit"], L["cor"] = "Anterior a esta execução", "cinza"
            else:
                L["at"] = "sem atestado"
                L["sit"], L["cor"] = "Pedir atestado", "amarelo"
        if dias <= 1 and not c:
            continue  # alocação de um dia só, sem atestado: ruído
        if not c and not fora:
            sem_itens.append({"emp": L["emp"], "_a": ti, "_b": tf or hoje, "per": per, "sit": "Pedir atestado"})
        linhas.append(L)
    # atestados que não casaram com nenhum emprego da ficha
    for a in ats:
        if id(a) in usados:
            continue
        per = ("%s a %s" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else "período não informado"
        st = {"anterior": ("Anterior a esta execução", "cinza"), "conferir": ("Conferir homologação", "cinza")}.get(
            a["_status"], ("Requerer remição (%s)" % _dias_txt(a["dias_remidos"]), "vermelho"))
        linhas.append({"emp": a.get("empresa") or "emprego não identificado na ficha", "per": per, "dias": a["dias_trabalhados"], "_ini": _d(a.get("periodo_inicio") or "") or _dp(a["data"]),
                       "at": at_txt(a), "at_full": at_full(a), "sit": st[0], "cor": st[1]})
        if a["_status"] != "anterior":
            _seg(a, a.get("empresa") or ((a.get("trechos") or [{}])[0].get("setor")) or "emprego não identificado na ficha", _d(a.get("periodo_inicio") or ""), _d(a.get("periodo_fim") or ""))
    # baixa de setor sem início registrado
    for b in f.get("baixas_sem_inicio", []):
        db = _dp(b["data"])
        if not db or (ult_at and db <= ult_at) or (ini_exec and db < ini_exec):
            continue
        ult = (" (último registro no setor: %s a %s)" % (b["ultimo_inicio"], b["ultimo_fim"] or "?")) if b.get("ultimo_inicio") else ""
        sem_itens.append({"emp": re.sub(r"^(PP|CC|A1|R1)\s*-\s*", "", b["setor"]), "_a": db - timedelta(days=1), "_b": db - timedelta(days=1), "per": "baixa em %s (sem início)" % _br(b["data"]),
                          "sit": "Pedir período e atestado"})
        linhas.append({"emp": re.sub(r"^(PP|CC|A1|R1)\s*-\s*", "", b["setor"]), "per": "início não registrado · baixa em %s%s" % (b["data"], ult), "dias": None, "_ini": db,
                       "at": "—", "sit": "Pedir período e atestado", "cor": "amarelo",
                       "sit_full": "A ficha registra a saída do setor, mas não a entrada: pedir à unidade o período trabalhado e o atestado."})
    linhas.sort(key=lambda L: L["_ini"] or date.min)
    tl = linha_unidades(f)
    for L in linhas:
        a0 = L.get("_ini")
        ds = re.findall(r"\d{2}[./]\d{2}[./]\d{4}", L["per"])
        b0 = (_dp(ds[1].replace("/", ".")) if len(ds) > 1 else None) or (hoje if ("em curso" in L["per"] or "hoje" in L["per"]) else a0)
        if L["per"].startswith("início não registrado") and a0:
            a0 = b0 = a0 - timedelta(days=1)  # a baixa é lançada na saída: vale a unidade que ele deixava
        L["un"], L["un_full"] = unidade_periodo(tl, a0, b0)
        L.pop("_ini", None)
        L["per"] = _br(L["per"])
        if L["per"].startswith("início não registrado"):
            L["per_full"] = L["per"]
            m_b = re.search(r"baixa em (\S+)", L["per"])
            L["per"] = "baixa em %s (sem início)" % (m_b.group(1) if m_b else "?")
        L["at"] = _br(L["at"])
        L["dias"] = rs.pl(L["dias"], "dia", "dias") if L.get("dias") else "—"
    # estudo (LEP, art. 126, § 1º, I: 1 dia a cada 12 h de frequência, divididas em no mínimo 3 dias)
    pend_est, conf_est = [], []
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
        else:
            dentro = next((o for o in ests if o is not e and o["_status"] in ("sem_remicao", "conferir") and o["_ini"] and e["_ini"] and o["_ini"] <= e["_ini"]
                           and (o["_fim"] or hoje) >= (e["_fim"] or hoje) and not e["_declaradas"]), None)
            if dentro:
                L["sit"], L["cor"] = "Já contada na matrícula de %s" % _br(dentro["inicio"]), "cinza"
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
    for e in pend_est:
        if e["_declaradas"]:
            horas_decl += e["_horas"]
            continue
        d, fim_e = e["_ini"], e["_fim"] or hoje
        while d and d <= fim_e:
            if d.weekday() < 5:
                dias_pend.add(d)
            d += timedelta(days=1)
    horas_pend = horas_decl + len(dias_pend) * HORAS_DIA_ESTUDO
    exec_ats = [a for a in ats if a["_status"] != "anterior"]
    pend = [a for a in ats if a["_status"] == "sem_remicao"]
    a_atestar = sum(int(re.match(r"\d+", L["dias"]).group()) for L in linhas if L["cor"] == "amarelo" and L["dias"] != "—" and L["at"].startswith("sem atestado"))
    est_exec = [e for e in ests if e["_status"] in ("sem_remicao", "conferir")]
    res = {"inicio_execucao": ini_exec, "remidos_execucao": sum(a["dias_remidos"] for a in exec_ats),
           "remidos_anteriores": sum(a["dias_remidos"] for a in ats if a["_status"] == "anterior"),
           "homologados": sum(i["dias"] for i in incs), "remicoes": incs,
           "pendentes": sum(a["dias_remidos"] for a in pend), "parciais": 0,
           "atestados_pendentes": pend, "atestados_parciais": [],
           "remidos_estudo": sum(e["_horas"] // 12 for e in est_exec), "estudos_pendentes": pend_est,
           "estudo_horas_pend": horas_pend, "estudo_dias_pend": horas_pend // 12,
           "dias_a_atestar": a_atestar, "baixas": sum(1 for L in linhas if L["per"].startswith("início não registrado"))}
    res["diferenca"] = res["remidos_execucao"] + res["remidos_estudo"] - res["homologados"]
    # ---- blocos da tela ----
    def _nome(x):
        x = re.sub(r"\s+", " ", x or "").strip()
        base, ext = (x[:-len(" (externo)")], " (externo)") if x.endswith(" (externo)") else (x, "")
        if base.isupper():
            base = base.title()
            # siglas (unidades, setores): voltam em maiúsculas
            base = re.sub(r"\b([A-Za-zÀ-ú]+)\b", lambda m: m.group(1).upper() if (m.group(1).upper() in (
                "CPAIG", "IPCG", "PTRAN", "EPJFC", "PDIB", "PED", "PHAC", "EPRACAG", "UMMVE", "CPAC", "ACM", "EJA", "EAD", "SENAC", "PV", "II", "III", "IV", "ST", "MS")
                or (len(m.group(1)) >= 2 and sum(ch in "AEIOUÁÉÍÓÚÂÊÔÃÕ" for ch in m.group(1).upper()) == 0)) else m.group(1), base)
            base = re.sub(r"(?<=\s)(Que|De|Da|Do|Das|Dos|E)\b", lambda m: m.group(1).lower(), base)
        return base + ext
    def _p(a0, b0):
        return "%s a %s" % (rs.fmt(a0), rs.fmt(b0)) if a0 and b0 and a0 != b0 else (rs.fmt(a0) if a0 else "período não informado")
    blocos = []
    for b in blocos_at.values():
        a = b["a"]
        if a["_status"] == "anterior":
            continue
        its = sorted(b["itens"], key=lambda i: i["_a"] or date.min)
        if len(its) > 1:  # trecho de um dia só (troca de setor no mesmo dia): ruído
            its = [i for i in its if not (i["_a"] and i["_b"] and i["_a"] >= i["_b"])] or its
        for i in its:
            i["un"] = unidade_periodo(tl, i["_a"], i["_b"])[0]
            i["per"] = _p(i["_a"], i["_b"])
            i["emp"] = _nome(i["emp"])
        num = (a.get("numero") or "s/n").split("/ST")[0]
        pend = a["_status"] == "sem_remicao"
        blocos.append({"tipo": "atestado", "chave": "fd:at:%s:%s" % (num, a["data"]), "_ord": its[0]["_a"] if its and its[0]["_a"] else _dp(a["data"]),
                       "titulo": "Atestado nº %s" % num, "info": "%s trabalhados · %s remidos" % (a["dias_trabalhados"], _fmtn(a["dias_remidos"])),
                       "sit": ("Requerer remição" if pend else "Conferir homologação"), "cor": ("vermelho" if pend else "cinza"),
                       "remidos": a["dias_remidos"],
                       "itens": [{"emp": i["emp"], "un": i["un"], "per": i["per"]} for i in its]})
    blocos.sort(key=lambda b: b["_ord"] or date.min)
    sem = []
    for i in sorted(sem_itens, key=lambda i: i["_a"] or date.min):
        un = unidade_periodo(tl, i["_a"], i["_b"])[0]
        sem.append({"emp": _nome(i["emp"]), "un": un, "per": _br(i["per"]), "sit": i["sit"], "cor": "amarelo",
                    "chave": "fd:sem:%s:%s" % (_norm(i["emp"]), _br(i["per"]))})
    if sem:
        blocos.append({"tipo": "sem", "titulo": "Sem atestado na ficha", "info": "procurar nos autos ou pedir à unidade", "itens": sem})
    est = [L for L in linhas if L["emp"].startswith("Estudo")]
    exs = [x for x in f.get("exames", []) if not ini_exec or (_dp(x["data"]) or date.max) >= ini_exec]
    if est or exs:
        blocos.append({"tipo": "estudo", "titulo": "Estudo", "info": "certidão de frequência", "itens": [
            {"emp": L["emp"].replace("Estudo · ", ""), "un": L.get("un") or "—", "per": "%s · %s" % (L["per"], L["at"]),
             "sit": ("Requerer remição" if L["sit"].startswith("Requerer") else ("Conferir homologação" if L["sit"].startswith("Conferir") else L["sit"]))
                    + (" · verificar acréscimo de 1/3 pela conclusão (LEP, art. 126, § 5º)" if "conclu" in (L.get("per_full") or "").lower() else ""),
             "cor": {"amarelo": "amarelo", "vermelho": "vermelho"}.get(L["cor"], "cinza"),
             "chave": "fd:est:%s:%s" % (_norm(L["emp"]), L["per"])} for L in est] + [
            {"emp": x["exame"], "un": unidade_periodo(tl, _dp(x["data"]), _dp(x["data"]))[0], "per": "certificado registrado em %s" % _br(x["data"]),
             "sit": "Conferir homologação · se certificou a conclusão do ensino, verificar o acréscimo de 1/3 (LEP, art. 126, § 5º)", "cor": "cinza",
             "chave": "fd:exa:%s:%s" % (_norm(x["exame"]), x["data"])} for x in exs]})
    for b in blocos:
        b.pop("_ord", None)
    res["blocos"] = blocos
    res["sem_n"] = len(sem)
    return linhas, res


def _dias_txt(v):
    """'1 dia' / '2,5 dias' / '3 dias'."""
    return "%s %s" % (_fmtn(v), "dia" if v == 1 else "dias")


def _br(txt):
    """dd.mm.aaaa e dd/mm/aa -> dd/mm/aaaa."""
    txt = re.sub(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", r"\1/\2/\3", txt or "")
    return re.sub(r"\b(\d{2})/(\d{2})/(\d{2})\b(?!/|\d)", lambda m: "%s/%s/%s" % (m.group(1), m.group(2), (2000 if int(m.group(3)) < 70 else 1900) + int(m.group(3))), txt)


def comparativo(r, f, hoje=None, conferidos=None, manuais=None):
    """Campos da aba Ficha disciplinar: colunas resumidas + uma linha por emprego (atestado x remição no RSPE)."""
    hoje = hoje or date.today()
    out = {"fd_tem": bool(f), "fd_cor": "cinza", "fd_sit": "Sem ficha", "fd_conduta": "", "fd_trab": "", "fd_remidos": "",
           "fd_atestar": "", "fd_estudo": "", "fd_faltas": "", "fd_linhas": [], "fd_dias": None}
    if not f:
        out["fd_linhas"] = [{"emp": "Ficha disciplinar não importada", "per": "", "dias": "", "at": "", "rspe": "", "sit": "Importe o PDF da Ficha Disciplinar (SIAPEN) pelo botão Importar PDFs", "cor": "cinza"}]
        return out
    linhas, res = quadro_trabalho(r, f, hoje)
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
            rem_man += rem
            info = " · ".join(x for x in [("nº %s" % d["numero"]) if d.get("numero") else "", ("%s trabalhados" % d["trabalhados"]) if d.get("trabalhados") else "",
                                          ("%s h" % d["horas"]) if d.get("horas") else "", ("%s remidos" % _fmtn(rem)) if rem else ""] if x)
            per = " a ".join(x for x in [d.get("inicio") or "", d.get("fim") or ""] if x) or "—"
            its.append({"emp": "%s%s" % (d.get("tipo") or "Outro", (" · " + d["descricao"]) if d.get("descricao") else ""), "un": d.get("unidade") or "—",
                        "per": per, "sit": info or "—", "cor": "", "id": m_["id"]})
        blocos.append({"tipo": "manual", "titulo": "Adicionados por você", "info": "fora da ficha (ex.: ENCCEJA, trabalho não registrado)", "itens": its})
    n_ok = sum(1 for b in blocos if b.get("ok")) + sum(1 for b in blocos for i in b["itens"] if i.get("ok"))
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
    out["fd_atestar"] = "Sim" if res.get("sem_n") else "Não"
    # situação: diz o que falta, sem rodeio (remição não homologada, trabalho sem atestado, estudo, baixa sem início)
    partes = []
    nh = res["pendentes"] or 0
    if nh:
        partes.append("Remição a requerer (%s de atestado sem remição posterior no RSPE)" % _dias_txt(nh))
    elif res["diferenca"] >= 1:
        partes.append("Conferir remição: ficha %s%s × RSPE %s" % ("≈ " if res["remidos_estudo"] else "", _dias_txt(ficha_total), _dias_txt(res["homologados"])))
    if res.get("sem_n"):
        partes.append("trabalho sem atestado (%d período%s)" % (res["sem_n"], "s" if res["sem_n"] > 1 else ""))
    if res["estudo_horas_pend"] >= 12:
        partes.append("estudo a requerer (≈ %s)" % rs.pl(res["estudo_dias_pend"], "dia", "dias"))
    if res["baixas"] and not partes:
        partes.append("trabalho sem início registrado")
    # último atestado há mais de 6 meses, com trabalho em curso
    ult = None
    for a in f.get("atestados", []):
        d = _d(a.get("periodo_fim") or "") or _d(a.get("data") or "")
        if d and (ult is None or d > ult):
            ult = d
    velho = bool(em and ult and (hoje - ult).days > 183)
    if velho:
        partes.append("último atestado há mais de 6 meses (período até %s)" % ult.strftime("%d/%m/%Y"))
    # situação objetiva na coluna; o texto completo fica no cabeçalho da linha expandida
    rot = []
    if nh or res["estudo_horas_pend"] >= 12:
        rot.append("Remição a requerer")
    if not nh and res["diferenca"] >= 1:
        rot.append("Conferir remição")
    if res.get("sem_n") or (res["baixas"] and not rot):
        rot.append("Ausência de atestado")
    if velho:
        rot.append("Último atestado há 6 meses")
    if partes:
        cor = "vermelho" if (nh or res["estudo_horas_pend"] >= 12) else "amarelo"
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
    out.update(fd_cor=cor, fd_sit=sit, fd_conduta=f.get("conduta") or "", fd_linhas=linhas,
               fd_blocos=blocos, fd_conf_n=n_ok, fd_conf_tot=marcaveis, fd_sem_n=res.get("sem_n", 0))
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


RE_SAIDA_LIVRE = re.compile(r"SA[ÍI]DA DA UNIDADE PENAL.*MOTIVO:\s*(ALVAR|SOLTURA|LIBERDADE|FUGA|EVAS|DETERMINA[ÇC][ÃA]O JUDICIAL|LIVRAMENTO|"
                            r"T[ÉE]RMINO|EXTIN|CUMPRIMENTO DE PENA|DOMICILIAR)|ALVAR[ÁA] DE SOLTURA|\bFUGA\b|EVADIU|EVAS[ÃA]O|FORAGID|N[ÃA]O RETORNOU", re.I)
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
        conc = [x for x in f.get("exames", []) if j13 <= (_dp(x["data"]) or date.min) <= ref and (not ini_exec or (_dp(x["data"]) or date.min) >= ini_exec)]
        conc += [{"exame": e["curso"].title(), "data": e.get("fim")} for a, b, e in estudos
                 if "CONCLU" in (e.get("motivo_fim") or "").upper() and j13 <= b <= ref and (not ini_exec or a >= ini_exec)]
        livres = [e for a, b, e in estudos if e.get("horas") and j13 <= b <= ref and (not ini_exec or a >= ini_exec) and "CONCLU" not in (e.get("motivo_fim") or "").upper()]
        if conc:
            res["XIII"] = (True, "ficha: %s" % "; ".join("%s (certificado registrado em %s)" % (x["exame"], _br(x["data"] or "")) for x in conc))
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
            r[k] = "A VERIFICAR: art. 9º, %s%s" % (", ".join(verif), aviso)
            r[k + "_status"] = "verificar"
            concl = "a verificar (%s)." % ", ".join(verif)
        else:
            r[k] = "não atinge: incisos conferidos na ficha disciplinar não atendidos" + aviso
            r[k + "_status"] = "nao"
            concl = "não atinge nenhum inciso nesta data (%s conferidos na ficha disciplinar)." % ", ".join(k2 for k2 in ("IV", "XI", "XII", "XIII") if k2 in res)
        r[k + "_explica"] = re.sub(r"^Conclusão: .*$", "Conclusão: " + concl, exp, flags=re.M) if exp else exp
