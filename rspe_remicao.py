"""Conciliação da remição pelo trabalho: ficha disciplinar (SIAPEN) x RSPE.

Etapas (cada uma documentada na função própria):
  1. vínculos de trabalho da ficha como máquina de estados (aberto do início até a baixa; nunca "baixa sem início";
     a baixa só é antecipada com prova em atestado - "baixa tardia");
  2. atestados da ficha (regex tolerante; vários segmentos por atestado, somados; atestado em lote/sem período com os
     períodos inferidos dos vínculos entre a última cobertura e a emissão; validação de capacidade e de 1/3);
  3. casamento atestado x remição do RSPE (só incidentes REMIÇÃO): número, dias iguais após truncar a fração, ordem
     cronológica. A cobertura vem do período do atestado; a data de referência só é checada (ref >= fim do período e
     ref <= decisão), sem janela e sem estender a cobertura;
  4. status: CONCILIADO, NAO_LANCADO (atestado emitido sem remição: verificar peticionamento), SEM_ATESTADO (pedir
     atestado), LACUNA (verificar se houve trabalho), DIVERGENCIA (dias diferentes além do truncamento);
  5. resíduo de fração (soma de trabalhados/3 exata x dias concedidos);
  6. estimativa seg.-sáb. só onde não há atestado nem remição;
  7. validações de datas.
Saída: tabela conciliada, pendências acionáveis e alertas de qualidade dos dados.
"""
import math
import re
from datetime import date, timedelta

import rspe_scraper as rs

DT = r"(\d{2}/\d{2}/\d{2,4})"
SEPD = r"\s*(?:A|À|ATÉ|ATE|-)\s*"

# nomes de setor que a ficha e os atestados usam para o mesmo vínculo: base jurídica, remicao.setores_sinonimos (editável sem
# mexer no programa); a lista abaixo só vale se a base não trouxer nenhuma
ALIAS_PADRAO = [(r"\bHORTA\b|\bAGS\b", "AGS", "Ags Prestadora - Me (Horta)"),
                (r"\bPAIVA\b", "PAIVA", "Paiva Lingerie")]


def sinonimos():
    try:
        import rspe_regras as rg
        lst = (rg.carregar().get("remicao") or {}).get("setores_sinonimos") or []
        out = [(x["padrao"], x["chave"], x.get("nome") or x["chave"]) for x in lst if x.get("padrao") and x.get("chave")]
        return out or ALIAS_PADRAO
    except Exception:
        return ALIAS_PADRAO


def _sa(t):
    return rs._sem_acento(t or "").upper()


def _dt(txt):
    """dd/mm/aa(aa) ou dd.mm.aaaa -> date (anos fora de 1900-2100: None)."""
    m = re.search(r"(\d{2})[./](\d{2})[./](\d{2,4})", txt or "")
    if not m:
        return None
    a = int(m.group(3))
    a = a + (2000 if a < 70 else 1900) if a < 100 else a
    try:
        d = date(a, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None
    return d if 1900 <= d.year <= 2100 else None


def _f(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _num(t):
    try:
        return float(str(t).replace(".", "").replace(",", ".")) if re.search(r",\d", str(t)) else float(str(t))
    except ValueError:
        return 0.0


def _fmtn(v):
    if v is None:
        return "—"
    return ("%d" % v) if abs(v - round(v)) < 1e-9 else ("%.2f" % v).replace(".", ",")


def setor_chave(nome):
    """(chave, nome de exibição) do setor: tira prefixos ("PP - ", "EMPRESA", "SETOR DE", "FUNÇÃO") e junta as variações."""
    u = _sa(nome).strip(" ,.;:-")
    u = re.sub(r"^(?:NA\s+|NO\s+)?(?:FUNCAO|SETOR(?: DE TRABALHO)?(?: DE)?|EMPRESA)\s+", "", u)
    u = re.sub(r"^(?:PP|CC|A1|R1)\s*-\s*", "", u).strip(" ,.;:-")
    u = re.sub(r"^EMPRESA\s+", "", u)
    for pad, ch, disp in sinonimos():
        if re.search(pad, u):
            return ch, disp
    ch = re.sub(r"\W", "", u)[:12] or "?"
    disp = " ".join(w.capitalize() if len(w) > 2 else w.lower() for w in u.split()) or "Setor não identificado"
    return ch, disp


def mesmo_setor(a, b):
    """Mesma chave, ou uma é o começo da outra ("POLIGONAL" x "POLIGONALENG")."""
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)))


# --------------------------------------------------------------------------- #
# Etapa 1 - vínculos
# --------------------------------------------------------------------------- #
RE_INI = [re.compile(r"INICIOU ATIVIDADES? LABORA(?:L|IS),?\s*(?:NO SETOR DE TRABALHO|NO SETOR(?: DE)?)\s*(.+?)(?:,\s*CONFORME|\s+CONFORME|$)"),
          re.compile(r"PASSA A EXERCER ATIVIDADE LABORAL,?\s*NO SETOR(?: DE)?\s*(.+?)(?:,\s*CONFORME|\s+CONFORME|$)")]
RE_FIM = [re.compile(r"DEIXA DE TRABALHAR,?\s*NO SETOR DE TRABALHO\s*(.+?)(?:,\s*CONFORME|\s+CONFORME|$)"),
          re.compile(r"ENCERROU ATIVIDADES? LABORA(?:L|IS),?\s*NO SETOR(?: DE)?\s*(.+?)(?:,|$)")]
RE_SAIDA = re.compile(r"SAIDA DA UNIDADE PENAL|EVASAO|TRANSFERENCIA|\bFUGA\b")


def vinculos(eventos, hoje):
    """Vínculos por setor: aberto no início, fechado na baixa do mesmo setor. Um novo início em OUTRO setor não fecha o
    anterior (nada se encerra por inferência); novo início no MESMO setor fecha o anterior na véspera (sem baixa na ficha).
    Baixa sem vínculo aberto: estende o último vínculo do setor encerrado por saída; sem nenhum, fica registrada como
    alerta (nunca como linha "baixa sem início")."""
    abertos, fechados, avisos = {}, [], []
    for e in eventos:
        d, u = _dt(e.get("data")), _sa(e.get("texto"))
        if not d:
            continue
        m = next((x for x in (p.search(u) for p in RE_INI) if x), None)
        if m:
            ch, disp = setor_chave(m.group(1))
            ch = next((k for k in abertos if mesmo_setor(k, ch)), ch)
            if ch in abertos:
                v = abertos.pop(ch)
                v.update(fim=d - timedelta(days=1), motivo_fim="sem baixa na ficha (novo início no mesmo setor)", sem_baixa=True)
                fechados.append(v)
            abertos[ch] = {"chave": ch, "setor": disp, "ini": d, "fim": None, "motivo_fim": "", "fim_ficha": None}
            continue
        m = next((x for x in (p.search(u) for p in RE_FIM) if x), None)
        if m:
            ch, disp = setor_chave(m.group(1))
            mm = re.search(r"MOTIVO:\s*(.+?)\s*\.?\s*$", u)
            mot = (mm.group(1).strip(" .") if mm else "") or "baixa"
            ch = next((k for k in abertos if mesmo_setor(k, ch)), ch)
            if ch in abertos:
                v = abertos.pop(ch)
                v.update(fim=d, fim_ficha=d, motivo_fim=mot)
                fechados.append(v)
            else:
                ult = [v for v in fechados if mesmo_setor(v["chave"], ch)]
                if ult and ult[-1].get("por_saida"):
                    ult[-1].update(fim=d, fim_ficha=d, motivo_fim=mot, por_saida=False)
                elif not ult:
                    avisos.append({"tipo": "baixa_sem_inicio", "data": d, "setor": disp})
            continue
        if abertos and RE_SAIDA.search(u):
            for ch in list(abertos):
                v = abertos.pop(ch)
                v.update(fim=d, fim_ficha=d, motivo_fim="saída/transferência/evasão", por_saida=True)
                fechados.append(v)
    out = fechados + list(abertos.values())
    out.sort(key=lambda v: v["ini"])
    return out, avisos


# --------------------------------------------------------------------------- #
# Etapa 2 - atestados
# --------------------------------------------------------------------------- #
RE_AT = re.compile(r"ATESTADO(?:\s+DE\s+TRABALHO)?(?:\s+PRISIONAL)?\s*(?:N\s*[.ºO°]?|Nº|N°|NO\.?)?\s*[.:]?\s*(\d{1,4})(?:\s*/\s*(\d{4}|[A-Z]{2,8}))?")
RE_SEG = re.compile(r"([^,;()]{2,60}?)\s*\(\s*" + DT + SEPD + DT + r"\s*\)\s*,?\s*(?:TOTALIZANDO\s*)?(\d+)\s*DIAS\s*TRABALHADOS\s*E\s*([\d.,]+)\s*(?:DIAS\s*)?REMIDOS")
RE_TOT = [re.compile(r"(\d+)\s*DIAS\s*TRABALHADOS\s*E\s*([\d.,]+)\s*(?:DIAS\s*)?(?:DE\s+)?REMI"),
          re.compile(r"(\d+)\s*DIAS DE TRABALHO\s*E\s*([\d.,]+)\s*DIAS DE (?:TEMPO DE )?REMICAO")]
RE_SO_REM = re.compile(r"(?:COM\s*)?([\d.,]+)\s*DIAS\s*DE\s*REMICAO")


def _limpa_setor(t):
    t = re.sub(r"^.*?\b(?:FUNCAO|SETOR DE|SETOR|NA EMPRESA|EMPRESA)\s+", "", t.strip(" ,.;:-"))
    return t.strip(" ,.;:-")


def atestados(eventos):
    """Atestados de trabalho da ficha, um por documento, com os segmentos (setor, período, trabalhados, remidos)."""
    out = []
    for e in eventos:
        d = _dt(e.get("data"))
        u = re.sub(r"\s+", " ", _sa(e.get("texto")))
        u = re.sub(r"\(\s*[A-Z ]{6,}\s*\)", " ", u)  # números por extenso entre parênteses
        if "ATESTADO" not in u or not d:
            continue
        if re.search(r"ATESTADO DE (?:PENA|CONDUTA|MATRICULA|FREQUENCIA|SAUDE|OBITO)|ATESTADO MEDICO", u):
            continue
        mn = RE_AT.search(u)
        segs = []
        for m in RE_SEG.finditer(u):
            nome = _limpa_setor(re.sub(r"^.*?(?:NO SISTEMA SEEU|AUTOS N?[ºO°]?\s*[\d.-]+)\s*,?", "", m.group(1)))
            segs.append({"setor_txt": nome, "ini": _dt(m.group(2)), "fim": _dt(m.group(3)), "trab": int(m.group(4)), "rem": _num(m.group(5)), "inferido": False})
        trab = rem = None
        if segs:
            trab, rem = sum(s["trab"] for s in segs), round(sum(s["rem"] for s in segs), 2)
        else:
            mt = next((x for x in (p.search(u) for p in RE_TOT) if x), None)
            if mt:
                trab, rem = int(mt.group(1)), _num(mt.group(2))
            else:
                ms = RE_SO_REM.search(u)
                if not ms:
                    continue
                rem = _num(ms.group(1))
            # período único: "período (trabalhado) de d a d" / "d a d"
            mp = re.search(r"PERIODO(?: TRABALHADO)?\s*(?:DE\s*)?" + DT + SEPD + DT, u) or re.search(DT + SEPD + DT, u)
            setor = ""
            ms_ = re.search(r"(?:NA FUNCAO|FUNCAO|SETOR(?: DE)?|NA EMPRESA)\s+(.+?)(?:\s+\(|\s+DE\s+\d|\s+\d{2}/|,|\.|\s+NAO RESTANDO|\s+COM\s+\d|$)", u)
            if ms_:
                setor = ms_.group(1).strip()
            if mp:
                segs.append({"setor_txt": setor, "ini": _dt(mp.group(1)), "fim": _dt(mp.group(2)), "trab": trab, "rem": rem, "inferido": False})
            else:
                # atestado em lote / sem período: os setores citados ("setor de A e B") delimitam a inferência
                nomes = [x.strip() for x in re.split(r"\s+E\s+|,", setor) if x.strip()] if setor else []
                segs = [{"setor_txt": n, "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True} for n in nomes] or \
                       [{"setor_txt": "", "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True}]
        for s in segs:
            s["chave"], s["setor"] = setor_chave(s["setor_txt"]) if s["setor_txt"] else (None, "")
        num = (mn.group(1).zfill(3) + ("/" + mn.group(2) if mn.group(2) else "")) if mn else ""
        out.append({"id": "at:%s:%s" % (num or "s/n", _f(d)), "numero": num, "emissao": d, "segs": segs, "trab": trab, "rem": rem,
                    "lote": any(s["inferido"] for s in segs), "origem": "ficha", "texto": e.get("texto", "")})
    out.sort(key=lambda a: a["emissao"])
    return out


def atestados_manuais(manuais):
    """Atestados de trabalho informados pelo operador ("+ Adicionar atestado"), com trechos opcionais."""
    out = []
    for m_ in manuais or []:
        d = m_.get("dados") or {}
        if (d.get("tipo") or "Trabalho") != "Trabalho":
            continue
        segs = []
        for ln in (d.get("trechos") or "").splitlines():
            p = [x.strip() for x in ln.split(";")]
            if len(p) >= 3 and _dt(p[1]) and _dt(p[2]):
                ch, disp = setor_chave(p[0])
                segs.append({"setor_txt": p[0], "chave": ch, "setor": disp, "ini": _dt(p[1]), "fim": _dt(p[2]),
                             "trab": int(_num(p[3])) if len(p) > 3 and p[3] else None, "rem": _num(p[4]) if len(p) > 4 and p[4] else None, "inferido": False})
        if not segs and _dt(d.get("inicio")) and _dt(d.get("fim")):
            ch, disp = setor_chave(d.get("descricao") or "") if d.get("descricao") else (None, "")
            segs.append({"setor_txt": d.get("descricao") or "", "chave": ch, "setor": disp, "ini": _dt(d["inicio"]), "fim": _dt(d["fim"]),
                         "trab": None, "rem": None, "inferido": False})
        trab = int(_num(d["trabalhados"])) if d.get("trabalhados") else (sum(s["trab"] or 0 for s in segs) or None)
        rem = _num(d["remidos"]) if d.get("remidos") else (round(sum(s["rem"] or 0 for s in segs), 2) or None)
        if not rem and not trab:
            continue
        emi = _dt(d.get("emissao") or "") or max((s["fim"] for s in segs if s["fim"]), default=None)
        if not emi:
            continue
        if not segs:
            segs = [{"setor_txt": "", "chave": None, "setor": "", "ini": None, "fim": None, "trab": None, "rem": None, "inferido": True}]
        num = (d.get("numero") or "").strip()
        out.append({"id": "man:%s" % m_.get("id"), "numero": num, "emissao": emi, "segs": segs, "trab": trab, "rem": rem,
                    "lote": any(s["inferido"] for s in segs), "origem": "operador", "texto": d.get("descricao") or ""})
    return out


# --------------------------------------------------------------------------- #
# Etapas 2-7
# --------------------------------------------------------------------------- #
def _dias_seg_sab(a, b):
    import rspe_ficha as rf
    return rf.dias_trabalho(a, b, "")


def remicoes_rspe(r):
    """Só incidentes REMIÇÃO concedidos, com dias, data da decisão e data de referência."""
    out = []
    for i in r.get("_incidentes", []):
        if not rs.e_remicao_concedida(i):
            continue
        m = re.search(r"([\d.,]+)\s*Dia", i.get("complemento", ""), re.I)
        if not m:
            continue
        dec = _dt(i.get("data_decisao") or "") or _dt(i.get("data_referencia") or "")
        ref = _dt(i.get("data_referencia") or "") or dec
        num = re.search(r"ATESTADO\D{0,12}(\d{1,4}(?:/\d{4})?)", _sa((i.get("complemento") or "") + " " + (i.get("motivo") or "")))
        out.append({"dias": _num(m.group(1)), "decisao": dec, "ref": ref, "numero": num.group(1) if num else "", "usada": None})
    out.sort(key=lambda x: x["decisao"] or date.min)
    return out


def conciliar(r, f, hoje=None, manuais=None, ini_exec=None, excluir_remicoes=None):
    """Concilia os atestados de trabalho da ficha (e os informados pelo operador) com as remições do RSPE.
    excluir_remicoes: datas de decisão de remições já atribuídas a outra origem (leitura, estudo)."""
    hoje = hoje or date.today()
    impressao = _dt(f.get("data_impressao") or "") or hoje
    evs = f.get("eventos") or []
    vinc, av_v = vinculos(evs, hoje)
    ats = atestados(evs) + atestados_manuais(manuais)
    ats.sort(key=lambda a: a["emissao"])
    rems = remicoes_rspe(r)
    for x in rems:
        if excluir_remicoes and (x["decisao"], x["dias"]) in excluir_remicoes:
            x["usada"] = "outra origem"
    alertas = []

    def alerta(tipo, texto, data=None):
        alertas.append({"tipo": tipo, "texto": texto, "data": data})

    for a in av_v:
        alerta("baixa sem início", "Baixa de %s em %s sem início registrado na ficha nem vínculo anterior do setor: conferir o período com a unidade." % (a["setor"], _f(a["data"])), a["data"])

    # ---- validação dos períodos explícitos (capacidade, ano trocado, 1/3) ----
    fim_ant = None
    for a in ats:
        for s in a["segs"]:
            if s["inferido"] or not s["ini"] or not s["fim"]:
                continue
            if s["fim"] < s["ini"]:
                alerta("data", "Atestado %s: fim (%s) anterior ao início (%s)." % (a["numero"] or "s/n", _f(s["fim"]), _f(s["ini"])), a["emissao"])
            corridos = (s["fim"] - s["ini"]).days + 1
            if s["trab"] and s["trab"] > corridos:
                prop = (fim_ant + timedelta(days=1)) if fim_ant and fim_ant < s["fim"] else None
                ok = prop and s["trab"] <= (s["fim"] - prop).days + 1
                alerta("erro de ano", "Atestado %s: %s dias trabalhados não cabem no período %s a %s (%s corridos) - possível erro de ano na ficha%s." % (
                    a["numero"] or "s/n", s["trab"], _f(s["ini"]), _f(s["fim"]), corridos,
                    ("; início provável %s (dia seguinte ao fim do atestado anterior)" % _f(prop)) if ok else ""), a["emissao"])
                if ok:
                    s["ini_ficha"], s["ini"], s["corrigido"] = s["ini"], prop, True
            if s["fim"] > impressao:
                alerta("data", "Atestado %s: período até %s, depois da impressão da ficha (%s)." % (a["numero"] or "s/n", _f(s["fim"]), _f(impressao)), a["emissao"])
        fs = [s["fim"] for s in a["segs"] if s["fim"]]
        if fs:
            fim_ant = max(fs + ([fim_ant] if fim_ant else []))
        if a["trab"] and a["rem"] is not None and abs(a["trab"] / 3.0 - a["rem"]) > 1:
            alerta("proporção", "Atestado %s: %s trabalhados dariam %s remidos (1 a cada 3), consta %s." % (
                a["numero"] or "s/n", a["trab"], _fmtn(a["trab"] / 3.0), _fmtn(a["rem"])), a["emissao"])

    # ---- Etapa 3: casamento atestado x remição ----
    def livre(x):
        return x["usada"] is None

    for a in ats:
        a["remicao"], a["status"] = None, "NAO_LANCADO"
        if a["rem"] is None:
            continue
        lim = a["emissao"] - timedelta(days=5)
        cand = [x for x in rems if livre(x) and (x["decisao"] or date.max) >= lim]
        x = next((x for x in cand if a["numero"] and x["numero"] and x["numero"].split("/")[0].zfill(3) == a["numero"].split("/")[0].zfill(3)), None) \
            or next((x for x in cand if int(math.floor(a["rem"] + 1e-9)) == int(math.floor(x["dias"] + 1e-9))), None)
        if x:
            x["usada"], a["remicao"], a["status"] = a["id"], x, "CONCILIADO"
    # (c) ordem cronológica: remição sem par exato entre esta emissão e a próxima -> divergência de dias
    for k, a in enumerate(ats):
        if a["remicao"] or a["rem"] is None:
            continue
        prox = min(next((b["emissao"] for b in ats[k + 1:] if b["emissao"] > a["emissao"]), date.max), a["emissao"] + timedelta(days=365))
        x = next((x for x in rems if livre(x) and a["emissao"] - timedelta(days=5) <= (x["decisao"] or date.max) < prox
                  and abs(x["dias"] - math.floor(a["rem"])) <= max(3, 0.3 * a["rem"])), None)
        if x:
            x["usada"], a["remicao"], a["status"] = a["id"], x, "DIVERGENCIA"

    # ENCCEJA/ENEM: remição concedida até 150 dias depois do certificado registrado na ficha é dele
    exames = []
    for ex in f.get("exames") or []:
        de = _dt(ex.get("data"))
        x = next((x for x in rems if livre(x) and de and de <= (x["decisao"] or date.min) <= de + timedelta(days=150)), None) if de else None
        if x:
            x["usada"] = "exame"
            exames.append("%s em %s: provável %s (certificado registrado em %s)" % (rs.pl(int(x["dias"]), "dia", "dias"), _f(x["decisao"]), ex.get("exame"), _f(de)))
    if exames:
        alerta("origem", "Remições atribuídas a exame (não ao trabalho): " + "; ".join(exames) + " - conferir na decisão.", None)
    # remição sem atestado na ficha: atestado não registrado (cobertura inferida até a data de referência), desde que haja
    # trabalho no período e nenhuma outra origem possível (estudo/leitura já excluídos)
    for x in rems:
        if not livre(x) or not x["ref"]:
            continue
        a = {"id": "rem:%s" % _f(x["decisao"]), "numero": "", "emissao": x["ref"], "segs": [{"setor_txt": "", "chave": None, "setor": "", "ini": None, "fim": None,
             "trab": None, "rem": None, "inferido": True}], "trab": None, "rem": x["dias"], "lote": True, "origem": "rspe", "texto": "",
             "remicao": x, "status": "CONCILIADO"}
        x["usada"] = a["id"]
        ats.append(a)
    ats.sort(key=lambda a: (max([s["fim"] for s in a["segs"] if s["fim"]] or [a["emissao"]]), a["emissao"]))

    # ---- prova em atestado: baixa tardia / vínculo sem baixa ----
    expl = [(a, s) for a in ats for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"]]
    for a, s in expl:  # setor do segmento sem nome: o vínculo da ficha no período
        if not s["chave"]:
            vs = [v for v in vinc if v["ini"] <= s["fim"] and (v["fim"] or hoje) >= s["ini"]]
            if len({v["chave"] for v in vs}) == 1:
                s["chave"], s["setor"] = vs[0]["chave"], vs[0]["setor"]
    for v in vinc:
        meus = [s for _, s in expl if mesmo_setor(s["chave"], v["chave"]) and s["fim"] >= v["ini"] and s["ini"] <= (v["fim"] or hoje)]
        if not meus:
            continue
        ult = max(meus, key=lambda s: s["fim"])
        fim_at = ult["fim"]
        doc = next(a for a, s in expl if s is ult)
        if (v["fim"] or hoje) <= fim_at + timedelta(days=1):
            continue
        # prova: outro setor atestado começando logo depois (transição documentada) e nenhum atestado do setor depois
        transicao = any(s["chave"] and not mesmo_setor(s["chave"], v["chave"]) and fim_at < s["ini"] <= fim_at + timedelta(days=31) for _, s in expl)
        depois = any(mesmo_setor(s["chave"], v["chave"]) and fim_at < s["ini"] <= (v["fim"] or hoje) for _, s in expl)
        if transicao and not depois:
            alerta("baixa tardia", "Baixa tardia na ficha: %s - ficha %s, atestado %s %s. Vale a data do atestado." % (
                v["setor"], ("baixa em " + _f(v["fim_ficha"])) if v.get("fim_ficha") else "sem baixa", doc["numero"] or "não registrado na ficha", _f(fim_at)), fim_at)
            v["fim_ficha_orig"], v["fim"], v["por_prova"] = v.get("fim_ficha"), fim_at, True
        elif v.get("sem_baixa"):
            alerta("baixa", "%s: vínculo sem baixa na ficha (encerrado na véspera do novo início, %s)." % (v["setor"], _f(v["fim"] + timedelta(days=1))), v["fim"])

    # ---- cobertura: segmentos inferidos (lote, sem período, remição sem atestado) ----
    E = sorted((s["ini"], s["fim"]) for _, s in expl)
    inferidos = []

    def _menos(x0, x1, cobs):
        livres = [(x0, x1)]
        for c0, c1 in cobs:
            nv = []
            for y0, y1 in livres:
                if c1 < y0 or c0 > y1:
                    nv.append((y0, y1))
                    continue
                if y0 < c0:
                    nv.append((y0, c0 - timedelta(days=1)))
                if c1 < y1:
                    nv.append((c1 + timedelta(days=1), y1))
            livres = nv
        return livres
    for a in sorted([a for a in ats if a["lote"]], key=lambda a: a["emissao"]):
        ult_cob = max([c1 for _, c1 in E + inferidos if c1 <= a["emissao"]] or [None]) if (E or inferidos) else None
        w0 = (ult_cob + timedelta(days=1)) if ult_cob else (min([v["ini"] for v in vinc] or [a["emissao"]]))
        if ini_exec and w0 < ini_exec:
            w0 = max(w0, min([v["ini"] for v in vinc if (v["fim"] or hoje) >= ini_exec] or [ini_exec]))
        w1 = a["emissao"]
        nomes = {s["chave"] for s in a["segs"] if s["chave"]}
        novos = []
        for v in vinc:
            a0, b0 = max(v["ini"], w0), min(v["fim"] or hoje, w1)
            if a0 <= b0 and (not nomes or any(mesmo_setor(v["chave"], n) for n in nomes)):
                for y0, y1 in _menos(a0, b0, E):
                    novos.append({"setor_txt": v["setor"], "chave": v["chave"], "setor": v["setor"], "ini": y0, "fim": y1, "trab": None, "rem": None, "inferido": True})
        if a["origem"] == "rspe" and not novos:
            # remição sem atestado e sem trabalho no período: origem não identificada (estudo, leitura, ENCCEJA...)
            a["status"], a["sem_origem"] = "SEM_ORIGEM", True
            continue
        a["segs"] = novos or [{"setor_txt": "", "chave": None, "setor": "não identificado na ficha", "ini": w0, "fim": w1, "trab": None, "rem": None, "inferido": True}]
        if a["trab"]:
            cap = sum((s["fim"] - s["ini"]).days + 1 for s in a["segs"])
            if a["trab"] > cap:
                alerta("capacidade", "Atestado %s: %s dias trabalhados não cabem nos períodos inferidos da ficha (%s dias corridos de %s a %s) - conferir o período no atestado." % (
                    a["numero"] or "s/n", a["trab"], cap, _f(w0), _f(w1)), a["emissao"])
        inferidos.append((w0, w1))
    so = [a for a in ats if a.get("status") == "SEM_ORIGEM"]
    if so:
        alerta("origem", "Remições sem atestado na ficha e sem trabalho no período (origem não identificada: estudo, leitura, ENCCEJA/ENEM ou atestado de "
                         "outra unidade): %s - conferir na decisão." % "; ".join("%s em %s" % (rs.pl(int(a["rem"]), "dia", "dias"), _f(a["remicao"]["decisao"])) for a in so), None)
    ats = [a for a in ats if a.get("status") != "SEM_ORIGEM"]

    # ---- coerência da data de referência (sem desfazer o casamento) ----
    for a in ats:
        x = a.get("remicao")
        if not x or a["origem"] == "rspe":
            continue
        fim_p = max([s["fim"] for s in a["segs"] if s["fim"]] or [None]) if any(s["fim"] for s in a["segs"]) else None
        if x["ref"] and fim_p and x["ref"] < fim_p:
            alerta("ref", "Remição de %s (atestado %s): data de referência %s anterior ao fim do período (%s)." % (
                rs.pl(int(x["dias"]), "dia", "dias"), a["numero"] or "s/n", _f(x["ref"]), _f(fim_p)), x["ref"])
        if x["ref"] and x["decisao"] and x["ref"] > x["decisao"]:
            alerta("ref", "Remição de %s: data de referência %s posterior à decisão %s." % (rs.pl(int(x["dias"]), "dia", "dias"), _f(x["ref"]), _f(x["decisao"])), x["ref"])

    # ---- sobreposição entre atestados (períodos explícitos) ----
    ex2 = [(a, s) for a in ats for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"]]
    for i, (a, s) in enumerate(ex2):
        for b, t in ex2[i + 1:]:
            if a is not b and s["ini"] <= t["fim"] and t["ini"] <= s["fim"] and min(s["fim"], t["fim"]) >= max(s["ini"], t["ini"]) + timedelta(days=1):
                alerta("sobreposição", "Atestados %s e %s com períodos sobrepostos (%s a %s)." % (a["numero"] or "s/n", b["numero"] or "s/n",
                                                                                              _f(max(s["ini"], t["ini"])), _f(min(s["fim"], t["fim"]))), max(s["ini"], t["ini"]))

    # ---- vínculos sobrepostos (sem prova para encerrar um deles) ----
    vv = [v for v in vinc if not ini_exec or (v["fim"] or hoje) >= ini_exec]
    for i, v in enumerate(vv):
        for w in vv[i + 1:]:
            a0, b0 = max(v["ini"], w["ini"]), min(v["fim"] or hoje, w["fim"] or hoje)
            if not mesmo_setor(v["chave"], w["chave"]) and (b0 - a0).days >= 7:
                alerta("vínculos sobrepostos", "Vínculos sobrepostos na ficha: %s e %s de %s a %s - conferir com a unidade qual setor valia (sem atestado que prove a baixa)." % (
                    v["setor"], w["setor"], _f(a0), _f(b0)), a0)

    # ---- Etapa 4: lacunas (entre segmentos explícitos do mesmo atestado e entre atestados consecutivos) ----
    pend = []
    for a in ats:
        ss = sorted([s for s in a["segs"] if not s["inferido"] and s["ini"] and s["fim"]], key=lambda s: s["ini"])
        for s, t in zip(ss, ss[1:]):
            if (t["ini"] - s["fim"]).days > 7:
                g0, g1 = s["fim"] + timedelta(days=1), t["ini"] - timedelta(days=1)
                alerta("lacuna", "Lacuna de %s a %s no atestado %s (entre %s e %s)." % (_f(g0), _f(g1), a["numero"] or "não registrado na ficha", s["setor"], t["setor"]), g0)
                pend.append({"data": g0, "status": "LACUNA", "texto": "%s a %s: sem vínculo comprovado (atestado %s)" % (_f(g0), _f(g1), a["numero"] or "s/n"),
                             "acao": "verificar se houve trabalho", "cor": "amarelo"})
    exp_docs = [(a, min(s["ini"] for s in a["segs"] if s["ini"]), max(s["fim"] for s in a["segs"] if s["fim"]))
                for a in ats if not a["lote"] and any(s["ini"] for s in a["segs"]) and any(s["fim"] for s in a["segs"])]
    for (a, _, f1), (b, i2, _) in zip(exp_docs, exp_docs[1:]):
        if (i2 - f1).days > 7 and (not ini_exec or f1 >= ini_exec):
            g0, g1 = f1 + timedelta(days=1), i2 - timedelta(days=1)
            alerta("lacuna", "Lacuna de %s a %s entre os atestados %s e %s." % (_f(g0), _f(g1), a["numero"] or "s/n", b["numero"] or "s/n"), g0)
            pend.append({"data": g0, "status": "LACUNA", "texto": "%s a %s: entre os atestados %s e %s" % (_f(g0), _f(g1), a["numero"] or "s/n", b["numero"] or "s/n"),
                         "acao": "verificar se houve trabalho", "cor": "amarelo"})

    # ---- Etapa 6: trabalho sem atestado nem remição (estimativa) ----
    cob = sorted([(s["ini"], s["fim"]) for a in ats for s in a["segs"] if s["ini"] and s["fim"]])
    sem = []
    for v in vinc:
        a0, b0 = v["ini"], v["fim"] or hoje
        if ini_exec and b0 < ini_exec:
            continue
        a0 = max(a0, ini_exec) if ini_exec else a0
        livres = [(a0, b0)]
        for c0, c1 in cob:
            nv = []
            for x0, x1 in livres:
                if c1 < x0 or c0 > x1:
                    nv.append((x0, x1))
                    continue
                if x0 < c0:
                    nv.append((x0, c0 - timedelta(days=1)))
                if c1 < x1:
                    nv.append((c1 + timedelta(days=1), x1))
            livres = nv
        for x0, x1 in livres:
            if (x1 - x0).days < 1:
                continue
            n = _dias_seg_sab(x0, x1)
            em_curso = v["fim"] is None and x1 == hoje
            sem.append({"setor": v["setor"], "ini": x0, "fim": x1, "em_curso": em_curso, "est": n})
            pend.append({"data": x0, "status": "SEM_ATESTADO", "texto": "%s, %s a %s: sem atestado nem remição (estimativa seg.-sáb.: ≈ %s, ≈ %d remidos)" % (
                v["setor"], _f(x0), "hoje (em curso)" if em_curso else _f(x1), rs.pl(n, "dia", "dias"), n // 3), "acao": "Pedir atestado", "cor": "amarelo"})

    # ---- pendências dos atestados ----
    for a in ats:
        if a["status"] == "NAO_LANCADO":
            if ini_exec and all(s["fim"] and s["fim"] < ini_exec for s in a["segs"]):
                a["status"] = "ANTERIOR"
                continue
            pend.append({"data": a["emissao"], "status": "NAO_LANCADO", "texto": "Atestado %s de %s (%s remidos) sem remição no RSPE" % (
                a["numero"] or "s/n", _f(a["emissao"]), _fmtn(a["rem"])), "acao": "verificar peticionamento no SEEU", "cor": "vermelho"})
        elif a["status"] == "DIVERGENCIA":
            pend.append({"data": a["emissao"], "status": "DIVERGENCIA", "texto": "Atestado %s: %s remidos x remição de %s no RSPE (%s)" % (
                a["numero"] or "s/n", _fmtn(a["rem"]), rs.pl(int(a["remicao"]["dias"]), "dia", "dias"), _f(a["remicao"]["decisao"])),
                "acao": "conferir a decisão e requerer a diferença" if a["remicao"]["dias"] < math.floor(a["rem"]) else "conferir a decisão", "cor": "amarelo"})
    pend.sort(key=lambda p: p["data"] or date.min)

    # ---- Etapa 5: resíduo de fração ----
    conc = [a for a in ats if a["status"] == "CONCILIADO" and a["trab"] and a["remicao"]]
    exato = sum(a["trab"] for a in conc) / 3.0
    conced = sum(int(math.floor(a["remicao"]["dias"] + 1e-9)) for a in conc)
    frac = [(a["numero"], a["rem"] - math.floor(a["rem"])) for a in conc if a["rem"] and a["rem"] - math.floor(a["rem"]) > 1e-6]
    residuo = int(math.floor(exato - conced + 1e-6)) if conc else 0
    if residuo >= 1:
        alerta("resíduo", "Resíduo de fração: %s trabalhados / 3 = %s; concedidos %s - possível resíduo de %s, conferir o entendimento do juízo (frações: %s)." % (
            sum(a["trab"] for a in conc), _fmtn(exato), conced, rs.pl(residuo, "dia", "dias"),
            "; ".join("%s: %s" % (n or "s/n", _fmtn(round(x, 2))) for n, x in frac) or "—"), None)

    # ---- tabela conciliada ----
    rot = {"CONCILIADO": ("Conciliado", "verde"), "NAO_LANCADO": ("Atestado emitido não lançado", "vermelho"),
           "DIVERGENCIA": ("Divergência de dias", "amarelo"), "ANTERIOR": ("Anterior a esta execução", "cinza")}
    tabela = []
    for a in ats:
        if a["status"] == "ANTERIOR":
            continue
        x = a.get("remicao")
        tit = ("Atestado nº %s" % a["numero"]) if a["numero"] else ("Atestado não registrado na ficha" if a["origem"] == "rspe" else "Atestado s/n")
        if a["origem"] == "operador":
            tit += " (informado por você)"
        nota = ""
        if a["lote"]:
            nota = ("períodos inferidos dos vínculos da ficha até a data de referência da remição; a ficha não registra o atestado" if a["origem"] == "rspe"
                    else "períodos inferidos da ficha; o texto do atestado não os detalha")
        tabela.append({"id": a["id"], "atestado": tit, "emissao": _f(a["emissao"]) if a["origem"] != "rspe" else "",
                       "segs": [{"setor": s["setor"] or "não identificado", "per": "%s a %s" % (_f(s["ini"]), _f(s["fim"])) if s["ini"] else "período não informado",
                                 "trab": s.get("trab"), "rem": s.get("rem"), "inferido": s["inferido"],
                                 "corrigido": ("ficha: %s" % _f(s["ini_ficha"])) if s.get("corrigido") else ""} for s in a["segs"]],
                       "trab": a["trab"], "rem": _fmtn(a["rem"]) if a["rem"] is not None else "—",
                       "rspe": rs.pl(int(x["dias"]), "dia", "dias") if x else "—", "decisao": _f(x["decisao"]) if x else "—", "ref": _f(x["ref"]) if x else "—",
                       "status": a["status"], "rot": rot[a["status"]][0], "cor": rot[a["status"]][1], "nota": nota,
                       "chave": "fd:at:%s:%s" % (a["numero"] or "s/n", _f(a["emissao"]).replace("/", "."))})
    alertas.sort(key=lambda x: x["data"] or date.min)
    return {"tabela": tabela, "pendencias": pend, "alertas": alertas, "vinculos": vinc, "atestados": ats, "remicoes": rems,
            "sem_atestado": sem, "residuo": residuo}
