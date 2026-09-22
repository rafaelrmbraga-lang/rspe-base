# -*- coding: utf-8 -*-
"""
Leitura da Ficha Disciplinar do SIAPEN (AGEPEN/MS) e confronto com o RSPE.

Extrai: identificação, conduta, períodos de trabalho (setor/empresa), atestados de trabalho
(dias trabalhados e remidos), faltas disciplinares (registro, PADIC, resultado), regressão/
restabelecimento e recusa de trabalho. Compara os dias remidos atestados com o saldo do RSPE
(LEP, arts. 126 a 128) e a existência de falta grave (LEP, arts. 50 e 83; CP, art. 83, III, b).
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
    return float(txt.replace(",", "."))


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
                ini = "%02d.%02d.%s" % (int(per.group(1)), MESES[per.group(2)], per.group(3))
                fim = "%02d.%02d.%s" % (int(per.group(4)), MESES[per.group(5)], per.group(6))
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
    f["cpf"] = (re.search(r"CPF:\s*(\d+)", cab) or [None, ""])[1]
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
        m = re.search(r"(\d+)\s*DIAS TRABALHADOS E\s*([\d.,]+)\s*DIAS REMIDOS", u)
        if not m:
            continue
        n = re.search(r"ATESTADO DE TRABALHO(?: PRISIONAL)?\W{0,3}\s*N\s*[.ºO°]*\s*([\w./-]+)", u)
        per = re.search(r"(?:PER[IÍ]ODO(?: TRABALHADO)?\s*(?:DE|NA EMPRESA[^\d]*)?)\s*(\d{2}/\d{2}/\d{2,4})\s*(?:A|-)?\s*(\d{2}/\d{2}/\d{2,4})", u)
        if not per:
            per = re.search(r"(\d{2}/\d{2}/\d{2,4})\s+(?:A\s+)?(\d{2}/\d{2}/\d{2,4})", u)
        emp = re.search(r"NA EMPRESA[,:]?\s*(.+?)\s+(?:\(|DE\s+\d|\d{2}/\d{2})", u)
        # trechos "NA/NO <setor> DE dd/mm/aa À dd/mm/aa" (um atestado pode cobrir vários empregos)
        trechos = [{"setor": t.group(1).strip(" ,.-"), "inicio": t.group(2), "fim": t.group(3)}
                   for t in re.finditer(r"\b(?:NA|NO|NAS|NOS)\s+(?:EMPRESA\s+)?([^,;]+?)\s+(?:DE\s+)?(\d{2}/\d{2}/\d{2,4})\s*(?:À|Á|A|ATÉ|-)\s*(\d{2}/\d{2}/\d{2,4})", u)]
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
                      "titulo": "Remição a requerer: atestado nº %s (%s), %s dias remidos" % ((a["numero"] or "s/n").split("/ST")[0], a["data"], _fmtn(a["dias_remidos"])),
                      "detalhe": "Atestado de %s dias trabalhados%s e nenhuma remição lançada no RSPE depois dele. Requerer a remição." % (a["dias_trabalhados"], per),
                      "fundamento": "LEP, arts. 126 (1 dia a cada 3 trabalhados) e 126, § 8º; Súmula 562 STJ."})
    if not res["atestados_pendentes"] and res["diferenca"] >= 1:
        itens.append({"nivel": "verificar",
                      "titulo": "Remição a conferir: ficha ≈ %s dias × RSPE %s dias" % (_fmtn(res["remidos_execucao"] + res["remidos_estudo"]), _fmtn(res["homologados"])),
                      "detalhe": "Os atestados e o estudo desta execução somam mais que as remições do RSPE. O RSPE não indica a origem de cada remição "
                                 "(trabalho, estudo, ENCCEJA/ENEM, leitura), então a diferença real pode ser maior: conferir nas decisões de remição.",
                      "fundamento": "LEP, art. 126."})
    # 2) proporção 1/3 nos atestados
    for a in ats:
        esperado = a["dias_trabalhados"] / 3.0
        if a["dias_trabalhados"] and abs(esperado - a["dias_remidos"]) > 1:
            itens.append({"nivel": "verificar", "titulo": "Atestado %s: %s dias trabalhados dariam %s remidos, consta %s" % (a["numero"] or a["data"], a["dias_trabalhados"], _fmtn(esperado), _fmtn(a["dias_remidos"])),
                          "detalhe": "Proporção legal: 1 dia de pena a cada 3 dias de trabalho.", "fundamento": "LEP, art. 126, § 1º, II."})
    # 3) trabalho sem atestado e baixas sem início registrado: um item cada, com a lista
    sem = [L for L in linhas if L["cor"] == "amarelo" and L["at"].startswith("sem atestado")]
    if sem:
        tot = sum(int(re.match(r"\d+", L["dias"]).group()) for L in sem if re.match(r"\d+", L["dias"]))
        itens.append({"nivel": "verificar", "titulo": "Trabalho sem atestado: %d período(s), ≈ %d dias (≈ %d remidos)" % (len(sem), tot, tot // 3),
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
                      "titulo": "Remição pelo estudo a requerer: ≈ %d h (≈ %d dias)" % (res["estudo_horas_pend"], res["estudo_dias_pend"]),
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
    res, faltas_rspe, _ = ra.perdas_por_falta(r.get("_incidentes", []))
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
            partes.append("%d dia%s (remição de %d dias lançada em %s, antes da falta de %s)" % (q, "s" if q > 1 else "", rem["n"], rem["data"], rs.fmt(f0)))
        if total >= 1:
            itens.append({"nivel": "verificar",
                          "titulo": "Perda de remidos pode alcançar remição anterior à falta de %s (≈ %d dias)" % (fa0["data_fato"], round(total)),
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
    return "%s atestado(s), %s dias remidos · %s" % (
        len(f.get("atestados", [])), _fmtn(f.get("dias_remidos_atestados") or 0),
        ("trabalhando em " + (em[-1].get("empresa") or em[-1].get("setor") or "?") + " desde " + em[-1]["inicio"]) if em else "sem trabalho em curso")


def _fmtn(v):
    v = float(v)
    return ("%d" % v) if abs(v - round(v)) < 0.01 else ("%.2f" % v)


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
        t = (i.get("tipo") or "").upper()
        if "REMI" in t and "PERDID" not in t and "NÃO" not in (i.get("situacao") or "").upper():
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
    Estudo: _status (sem_remicao | conferir | anterior | curto)."""
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
        return [i for i in incs if max(i["d"] or date.min, i["ref"] or date.min) >= (d0 or date.min) - timedelta(days=5)]
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
        if ini and (e["_fim"] or hoje) < ini:
            e["_status"] = "anterior"
        elif ((e["_fim"] or hoje) - (e["_ini"] or hoje)).days < 3:
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
    """Unidade(s) em que a pessoa estava entre a e b: a última entrada até o início e as entradas no meio
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

    def at_txt(a):
        return "nº %s · %s remidos" % ((a["numero"] or "s/n").split("/ST")[0], _fmtn(a["dias_remidos"]))

    def at_full(a):
        return "Atestado nº %s de %s: %s dias trabalhados, %s remidos%s" % ((a["numero"] or "s/n").split("/ST")[0], _br(a["data"]), a["dias_trabalhados"], _fmtn(a["dias_remidos"]),
                                                                          (" (%s a %s)" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else "")

    for t in trab:
        ti, tf = _dp(t["inicio"]), _dp(t.get("fim") or "")
        dias = ((tf or hoje) - ti).days + 1
        per = "%s a %s" % (t["inicio"], t["fim"]) if tf else "%s em diante (em curso)" % t["inicio"]
        c = cob[id(t)]
        fora = ini_exec and (tf or hoje) < ini_exec
        L = {"emp": _nome_emprego(t) + (" (externo)" if t.get("externo") else ""), "per": per, "dias": dias, "_ini": ti}
        if c:
            xs = [x for x, _, _ in c]
            L["at"] = "; ".join(at_txt(x) for x in xs)
            L["at_full"] = "; ".join(at_full(x) for x in xs)
            pend = [x for x in xs if x["_status"] == "sem_remicao"]
            if pend:
                L["sit"] = "Requerer remição (%s dias)" % _fmtn(sum(x["dias_remidos"] for x in pend))
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
                      "at": "sem atestado", "at_full": "Trabalho posterior ao último atestado da ficha.", "sit": "Requerer atestado (≈ %d remidos)" % (nd // 3), "cor": "amarelo"}
                linhas.append(L)
                linhas.append(L2)
                continue
        else:
            L["at"] = "—"
            if fora:
                L["sit"], L["cor"] = "Anterior a esta execução", "cinza"
            else:
                L["at"] = "sem atestado"
                L["sit"], L["cor"] = "Requerer atestado (≈ %d remidos)" % (dias // 3), "amarelo"
        if dias <= 1 and not c:
            continue  # alocação de um dia só, sem atestado: ruído
        linhas.append(L)
    # atestados que não casaram com nenhum emprego da ficha
    for a in ats:
        if id(a) in usados:
            continue
        per = ("%s a %s" % (a["periodo_inicio"], a["periodo_fim"])) if a.get("periodo_inicio") else "período não informado"
        st = {"anterior": ("Anterior a esta execução", "cinza"), "conferir": ("Conferir homologação", "cinza")}.get(
            a["_status"], ("Requerer remição (%s dias)" % _fmtn(a["dias_remidos"]), "vermelho"))
        linhas.append({"emp": a.get("empresa") or "emprego não identificado na ficha", "per": per, "dias": a["dias_trabalhados"], "_ini": _d(a.get("periodo_inicio") or "") or _dp(a["data"]),
                       "at": at_txt(a), "at_full": at_full(a), "sit": st[0], "cor": st[1]})
    # baixa de setor sem início registrado
    for b in f.get("baixas_sem_inicio", []):
        db = _dp(b["data"])
        if not db or (ult_at and db <= ult_at) or (ini_exec and db < ini_exec):
            continue
        ult = (" (último registro no setor: %s a %s)" % (b["ultimo_inicio"], b["ultimo_fim"] or "?")) if b.get("ultimo_inicio") else ""
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
        L["dias"] = ("%d dias" % L["dias"]) if L.get("dias") else "—"
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
             "dias": "%d dias úteis" % du if du else "—", "at": horas_txt,
             "at_full": ("Carga horária declarada na ficha." if e["_declaradas"] else "Estimativa: %d dias úteis × %d h por dia (como nas certidões da EJA)." % (du, HORAS_DIA_ESTUDO))}
        L["un"], L["un_full"] = unidade_periodo(tl, e["_ini"], e["_fim"] or hoje)
        dias_e = e["_horas"] // 12
        if e["_status"] == "curto":
            L["sit"], L["cor"] = "Menos de 3 dias: sem remição", "cinza"
        else:
            dentro = next((o for o in ests if o is not e and o["_status"] in ("sem_remicao", "conferir") and o["_ini"] and e["_ini"] and o["_ini"] <= e["_ini"]
                           and (o["_fim"] or hoje) >= (e["_fim"] or hoje) and not e["_declaradas"]), None)
            if dentro:
                L["sit"], L["cor"] = "Já contada na matrícula de %s" % _br(dentro["inicio"]), "cinza"
            elif e["_status"] == "sem_remicao":
                L["sit"], L["cor"] = "Requerer remição (≈ %d dias)" % dias_e, "amarelo"
                L["sit_full"] = "Nenhuma remição lançada no RSPE depois do início do estudo: requerer a certidão de frequência e a remição."
                pend_est.append(e)
            else:
                # parte do estudo posterior à última remição lançada no RSPE: certamente ainda sem remição
                fim_e2 = e["_fim"] or hoje
                if ult_rem and not e["_declaradas"] and fim_e2 > ult_rem:
                    ini2 = max(e["_ini"], ult_rem + timedelta(days=1))
                    h2 = _dias_uteis(ini2, fim_e2) * HORAS_DIA_ESTUDO
                    if h2 >= 12:
                        pend_est.append(dict(e, _ini=ini2, _horas=h2))
                        L["sit"], L["cor"] = ("Requerer remição após %s (≈ %d dias)" % (rs.fmt(ult_rem), h2 // 12)), "amarelo"
                        L["sit_full"] = "O período posterior à última remição do RSPE (%s) ainda não pode ter sido homologado; o anterior, conferir na decisão." % rs.fmt(ult_rem)
                        conf_est.append(e)
                        linhas.append(L)
                        continue
                L["sit"], L["cor"] = "Conferir homologação (≈ %d dias)" % dias_e, "cinza"
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
    return linhas, res


def _br(txt):
    """dd.mm.aaaa e dd/mm/aa -> dd/mm/aaaa."""
    txt = re.sub(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", r"\1/\2/\3", txt or "")
    return re.sub(r"\b(\d{2})/(\d{2})/(\d{2})\b(?!/|\d)", lambda m: "%s/%s/%s" % (m.group(1), m.group(2), (2000 if int(m.group(3)) < 70 else 1900) + int(m.group(3))), txt)


def comparativo(r, f, hoje=None):
    """Campos da aba Ficha disciplinar: colunas resumidas + uma linha por emprego (atestado x remição no RSPE)."""
    hoje = hoje or date.today()
    out = {"fd_tem": bool(f), "fd_cor": "cinza", "fd_sit": "Sem ficha", "fd_conduta": "", "fd_trab": "", "fd_remidos": "",
           "fd_atestar": "", "fd_estudo": "", "fd_faltas": "", "fd_linhas": [], "fd_dias": None}
    if not f:
        out["fd_linhas"] = [{"emp": "Ficha disciplinar não importada", "per": "", "dias": "", "at": "", "rspe": "", "sit": "Importe o PDF da Ficha Disciplinar (SIAPEN) pelo botão Importar PDFs", "cor": "cinza"}]
        return out
    linhas, res = quadro_trabalho(r, f, hoje)
    # trabalho anterior a esta execução: fica só no resumo do cabeçalho
    linhas = [L for L in linhas if L["sit"] != "Anterior a esta execução"]
    trab = f.get("trabalho", [])
    em = [x for x in trab if not x.get("fim")]
    out["fd_trab"] = ("%s desde %s" % (_nome_emprego(em[-1]), em[-1]["inicio"])) if em else "sem trabalho em curso"
    ficha_total = res["remidos_execucao"] + res["remidos_estudo"]
    out["fd_remidos"] = "%s / %s" % (_fmtn(ficha_total), _fmtn(res["homologados"]))
    out["fd_estudo"] = ("≈ %d h (≈ %d dias)" % (res["estudo_horas_pend"], res["estudo_dias_pend"])) if res["estudo_horas_pend"] >= 12 else ""
    out["fd_atestar"] = ("≈ %d dias (≈ %d remidos)" % (res["dias_a_atestar"], res["dias_a_atestar"] // 3)) if res["dias_a_atestar"] else ""
    # situação: diz o que falta, sem rodeio (remição não homologada, trabalho sem atestado, estudo, baixa sem início)
    partes = []
    nh = res["pendentes"] or 0
    if nh:
        partes.append("Remição a requerer (%s dias de atestado sem remição posterior no RSPE)" % _fmtn(nh))
    elif res["diferenca"] >= 1:
        partes.append("Conferir remição: ficha %s%s × RSPE %s dias" % ("≈ " if res["remidos_estudo"] else "", _fmtn(ficha_total), _fmtn(res["homologados"])))
    if res["dias_a_atestar"]:
        partes.append("trabalho sem atestado (≈ %d dias)" % res["dias_a_atestar"])
    if res["estudo_horas_pend"] >= 12:
        partes.append("estudo a requerer (≈ %d dias)" % res["estudo_dias_pend"])
    if res["baixas"] and not partes:
        partes.append("trabalho sem início registrado")
    if partes:
        cor = "vermelho" if nh else "amarelo"
        sit = "; ".join(partes)
        sit = sit[0].upper() + sit[1:]
    else:
        cor, sit = "verde", "Em ordem"
    faltas = f.get("faltas", [])
    out["fd_faltas"] = ("%d (%s)" % (len(faltas), ", ".join(x["situacao"] for x in faltas))) if faltas else "nenhuma"
    out["fd_remicoes"] = ("Remições no RSPE: " + " · ".join("%s dias em %s" % (_fmtn(i["dias"]), i["data"]) for i in res["remicoes"]) +
                          ". O RSPE não diz a origem de cada uma (trabalho, estudo, ENCCEJA/ENEM, leitura).") if res["remicoes"] else "Nenhuma remição no RSPE."
    out["fd_resumo_exec"] = "atestados: %s dias · estudo: ≈ %s dias · RSPE: %s dias%s%s" % (
        _fmtn(res["remidos_execucao"]), _fmtn(res["remidos_estudo"]), _fmtn(res["homologados"]), "",
        (" · anteriores a esta execução: %s dias" % _fmtn(res["remidos_anteriores"])) if res["remidos_anteriores"] else "")
    out.update(fd_cor=cor, fd_sit=sit, fd_conduta=f.get("conduta") or "", fd_linhas=linhas)
    return out
