# -*- coding: utf-8 -*-
"""Painel do APTO na página do processo do SEEU: a análise de UM processo, pronta para mostrar.

Roda na extensão (Pyodide, no navegador), SEM o APTO: as abas do processo no SEEU viram o registro no formato do RSPE pelo
leitor do APTO (rspe_seeu_abas -> rspe_scraper), e o cálculo é o do APTO (rspe_motor._montar_modelo), sem conta nova. Aqui
só se escolhe o que mostrar e em que ordem - a da ficha do assistido no APTO: pena e data-base, marcos (progressão,
livramento, término), benefícios (indulto, comutação, prescrição, extinção, saída temporária) e os demais pontos.

Duas situações só (decisão de 11/2026): VERDE = confere (há certeza: o dado do SEEU e o cálculo fecham, sem pendência);
AMARELO = conferir (dúvida no cálculo, dado que as abas não trazem, ou requisito que depende da ficha disciplinar). Sem
"agir já" e sem escala de urgência. Sem a ficha, o que depende dela (falta grave, comportamento, trabalho) nunca é verde.
Custodiado sem remição decidida há mais de 6 meses: conferir o atestado de trabalho ou estudo.
A assinatura do resultado (sha1 do painel) e a chave da entrada (rspe_motor._chave_calculo) permitem conferir que o
navegador e o Python do APTO chegam ao mesmo resultado para a mesma entrada (teste de paridade na compilação)."""
import copy
import hashlib
import json
import re
from datetime import date

import rspe_motor as mt
import rspe_regras as rg
import rspe_scraper as rs
import rspe_view as rv

VERSAO_PAINEL = 3
SEM_ATESTADO_DIAS = 180
PROXIMO_DIAS = 60
FICHA_VALIDADE_DIAS = 90   # ficha impressa há mais de 90 dias: conferir a atual (a mesma regra da aba Ficha do APTO)         # marco a até 60 dias: destaque de "próximo"  # 6 meses sem remição decidida, custodiado: pedir atestado

CTX_VAZIO = {"baixas": {}, "fichas": {}, "manuais": {}, "ajustes": {}, "dmanuais": {}, "peds": {}, "hist_n": {}, "fixados": {},
             "homonimos": {}, "outras_cond": {}, "outros_procs": {}, "outras_exec": {}, "homon_det": {}}

# Painel v2 (11/2026, decisão do usuário): sem "agir já" e sem escala de urgência; tudo é para CONFERIR, em duas cores:
#   verde   = há certeza (o dado do SEEU e o cálculo do APTO fecham, sem ponto pendente);
#   amarelo = conferir (dúvida no cálculo, dado que o SEEU não traz, ou requisito que depende da ficha disciplinar).
# A ordem segue a ficha do assistido no APTO: pena e data-base, os marcos (progressão, livramento, término), os benefícios
# (indulto, comutação, prescrição, extinção, saída temporária) e depois os demais pontos (auditoria, atestado, crimes).
DUVIDA = re.compile(r"verificar|conferir|ver auditoria|a apurar|\?|n[aã]o consta no rspe|n[aã]o calculou|tese|diverg", re.I)
NAO_SE_APLICA = re.compile(r"^(n[aã]o se aplica|pena cumprida|pena interrompida|pena suspensa)", re.I)

DECRETOS = [("i25", "exp25", "Indulto 2025", "Decreto 12.790/2025"), ("c25", "cexp25", "Comutação 2025", "Decreto 12.790/2025"),
            ("i24", "exp24", "Indulto 2024", "Decreto 12.338/2024"), ("c24", "cexp24", "Comutação 2024", "Decreto 12.338/2024"),
            ("i22", "exp22", "Indulto 2022", "Decreto 11.302/2022")]
NAO_CABE = re.compile(r"^(vedad|n[aã]o atinge|n[aã]o alcan|fato posterior|prejudicad|n[aã]o se aplica|falta|n[aã]o cab)", re.I)
DECIDIDO = re.compile(r"^(concedid|indeferid)", re.I)  # o juízo já decidiu (consta no RSPE): não alerta
# avisos da auditoria que pedem o MESMO recálculo (a progressão já decidida, refeita com o que mudou depois dela): um cartão só
RECALCULO_PROGRESSAO = {"remicao-preterita-apos-progressao": "remição", "semiaberto-referencia-desatualizada": "redução da pena"}
# ícones dos benefícios nos chips da página (tipo, rótulo, ids dos cartões do painel), na ordem em que aparecem
ICONES = [("st", "Saída temporária", ("st",)), ("pa", "Progressão antecipada", ("pa",)), ("ind", "Indulto", ("i25", "i24", "i22")),
          ("com", "Comutação", ("c25", "c24")), ("ext", "Extinção", ("ext",)), ("presc", "Prescrição", ("presc",)),
          ("rem", "Remição pendente", ("rem",))]
# avisos de cadastro que não mudam o cálculo nem o que pedir pelo assistido: ficam numa seção recolhida, fora dos alertas
SEM_EFEITO = re.compile(r"^(Pena na ficha .* difere da pena total do RSPE|Data impossível no cadastro)", re.I)
PROXIMO = {"fechado": "semiaberto", "semiaberto": "aberto"}
ORDEM = {"verde": 0, "amarelo": 1}  # compatibilidade com testes e com a lingueta


def _linhas(txt, n=8):
    return [x.strip() for x in str(txt or "").split("\n") if x.strip()][:n]


def _item(id_, certo, titulo, valor="", motivo="", conferir="", conta=None, fundamento=""):
    """Um ponto do painel. certo=True só quando não há nada pendente (verde); qualquer pendência = amarelo, com o que conferir."""
    st = "verde" if certo and not conferir else "amarelo"
    return {"id": id_, "status": st, "status_txt": "Confere" if st == "verde" else "Conferir", "titulo": titulo, "valor": valor or "",
            "motivo": motivo or "", "conferir": conferir or "", "conta": [c for c in (conta or []) if c], "fundamento": fundamento or ""}


def _sem_ficha(m):
    return not m.get("ficha_tem")


def _custodiado(r, m):
    reg = rs._sem_acento(m.get("regime") or "").lower()
    st = rs._sem_acento(r.get("status_execucao") or r.get("regime_atual") or "").upper()
    return ("fechado" in reg or "semiaberto" in reg) and "ATIVO" in st and not m.get("interrompida")


def _ultima_remicao(r):
    ds = [rs.to_date(i.get("data_decisao") or i.get("data_referencia") or "") for i in r.get("_incidentes") or []
          if "REMI" in rs._sem_acento(i.get("tipo") or "").upper() and (i.get("situacao") or "").upper() == "CONCEDIDO"]
    ds = [d for d in ds if d]
    return max(ds) if ds else None


def _inicio_custodia(r):
    ds = [rs.to_date(e.get("data") or "") for e in r.get("_eventos") or [] if "PRIS" in rs._sem_acento(e.get("tipo") or "").upper()]
    ds = [d for d in ds if d]
    return max(ds) if ds else None


def _extenso(n):
    """dias -> "1 ano, 2 meses e 14 dias" (convenção do SEEU: ano de 365, mês de 30)."""
    a, r_ = divmod(int(n), 365)
    m, d = divmod(r_, 30)
    if m == 12:  # 360 a 364 dias de resto: 11 meses e 30+ dias não existe na convenção; fica em meses e dias
        m, d = 11, d + 30
    partes = [x for x in (rs.pl(a, "ano", "anos") if a else "", rs.pl(m, "mês", "meses") if m else "", rs.pl(d, "dia", "dias") if d else "") if x]
    return " e ".join([", ".join(partes[:-1]), partes[-1]]) if len(partes) > 1 else (partes[0] if partes else "0 dias")


def _quando(d_txt, hoje):
    """Distância até a data, como fato (sem urgência): 'atingida há 2 meses e 18 dias', 'faltam 4 anos e 7 dias'."""
    d = rs.to_date(d_txt or "")
    if not d:
        return ""
    n = (d - hoje).days
    if n < 0:
        return "atingida há " + _extenso(-n)
    if n == 0:
        return "atingida hoje"
    return "faltam " + _extenso(n)


def montar(r, m, hoje, faltou=None, fichas_n=0):
    """Painel a partir do registro (r) e do modelo do APTO (m, já em json_seguro). faltou: o que a leitura das abas não achou."""
    sem_ficha = _sem_ficha(m)
    reg = (m.get("regime") or "").strip()
    reg_l = rs._sem_acento(reg).lower()
    marcos, beneficios, demais, nao_cabe, observacoes = [], [], [], [], []
    ficha_txt = "comportamento carcerário e falta grave (ficha disciplinar)"

    # ---- pena e data-base (como o topo da ficha do assistido)
    t, c = m.get("pena_total_dias"), m.get("pena_cumprida_dias")
    pct = max(0, min(100, round(c * 100 / t))) if isinstance(t, (int, float)) and t and isinstance(c, (int, float)) else None
    # formato curto do SEEU (o mesmo da capa do processo), que cabe na coluna; sem ele, o do APTO por extenso
    pena = {"total": r.get("pena_total") or m.get("pena_total") or "—", "cumprida": r.get("pena_cumprida") or m.get("pena_cumprida") or "—",
            "remanescente": r.get("pena_remanescente") or m.get("pena_rem") or "—",
            "termino": m.get("termino") or "—", "pct": pct, "regime": reg, "aviso": m.get("motivo_exec") or ""}
    db_duv = (m.get("db_cor") or "") in ("amarelo", "vermelho", "laranja")
    marcos.append(_item("db", not db_duv, "Data-base (progressão)", m.get("db") or "—", m.get("db_motivo") or "",
                        "data-base divergente ou não informada pelo SEEU: conferir os marcos interruptivos" if db_duv else "",
                        [], "LEP, art. 112; STJ, Súmula 534"))

    # ---- marcos: a certeza é da DATA (o requisito subjetivo fica dito, não muda a cor do marco)
    ps = m.get("prog_sit") or ""
    if m.get("prog") and m.get("prog") != "—" and not NAO_SE_APLICA.match(ps):
        prox = next((v for k, v in PROXIMO.items() if k in reg_l), "")
        duv = bool(DUVIDA.search(ps))  # a cor do APTO na progressão é de proximidade, não de dúvida: a dúvida vem do texto
        marcos.append(_item("prog", not duv, "Progressão ao " + prox if prox else "Progressão de regime", m.get("prog"),
                            "; ".join(x for x in (_quando(m.get("prog"), hoje), "fração " + m["frac_prog"] if m.get("frac_prog") else "") if x),
                            ps if duv else "",
                            ["Data-base: %s" % m["dbase"] if m.get("dbase") else "", "Fração: %s" % m["frac_prog"] if m.get("frac_prog") else "",
                             "Pena cumprida: %s" % m["pena_cumprida"] if m.get("pena_cumprida") else "",
                             "Pena a cumprir: %s" % m["pena_rem"] if m.get("pena_rem") else "",
                             "Requisito subjetivo: " + ficha_txt if sem_ficha else ""], "LEP, art. 112"))
    ls = m.get("liv_sit") or ""
    if re.match(r"vedad|n[aã]o cab", ls, re.I):
        nao_cabe.append({"titulo": "Livramento condicional", "motivo": ls})
    elif m.get("liv") and m.get("liv") != "—" and not NAO_SE_APLICA.match(ls):
        duv = bool(DUVIDA.search(ls))
        marcos.append(_item("liv", not duv, "Livramento condicional", m.get("liv"),
                            "; ".join(x for x in (_quando(m.get("liv"), hoje), "fração " + m["frac_liv"] if m.get("frac_liv") else "") if x),
                            ls if duv else "",
                            ["Fração: %s" % m["frac_liv"] if m.get("frac_liv") else "",
                             m.get("liv_motivo") if m.get("liv_motivo") != m.get("liv") else "",
                             "Requisito subjetivo: comportamento satisfatório e sem falta grave em 12 meses (ficha disciplinar)" if sem_ficha else ""],
                            "CP, art. 83"))
    if m.get("termino") and m.get("termino") != "—":
        tm = m.get("termino_motivo") if m.get("termino_motivo") != m.get("termino") else ""
        seeu = r.get("termino_previsao_seeu") or ""
        dif = bool(seeu and rs.to_date(seeu) and rs.to_date(m.get("termino")) and rs.to_date(seeu) != rs.to_date(m.get("termino")))
        marcos.append(_item("term", not (DUVIDA.search(tm or "") or dif), "Término da pena", m.get("termino"),
                            "; ".join(x for x in (_quando(m.get("termino"), hoje), ("SEEU: " + seeu) if dif else "") if x),
                            "o término do APTO (com remição) difere do previsto pelo SEEU" if dif else (tm if DUVIDA.search(tm or "") else ""),
                            ["Saldo de remição: " + (m.get("remidos") or "0 dias"), tm], "CP, art. 82; LEP, art. 126"))

    # ---- benefícios
    es = m.get("ext_sit") or ""
    if re.match(r"extin[cç][aã]o (cab|a verificar)|t[eé]rmino em", es, re.I):
        duv = bool(DUVIDA.search(es))
        beneficios.append(_item("ext", not duv, "Extinção da pena", "cabível" if not duv else "a verificar", es if not duv else "",
                                es if duv else "", _linhas(m.get("ext_hipoteses"), 4), "CP, art. 82; LEP, art. 146"))
    pp = m.get("presc_ppe") or ""
    if pp:
        certo = bool(re.match(r"n[aã]o prescrita", pp, re.I))
        if certo or re.match(r"aparente|iminente|a verificar", pp, re.I):
            beneficios.append(_item("presc", certo, "Prescrição executória", "não aparente" if certo else pp.lower(),
                                    ("próximo marco " + m["presc_prox"]) if certo and m.get("presc_prox") else "",
                                    "" if certo else (m.get("presc_ppe_full") or pp) + ": conferir os marcos interruptivos e as datas na ação penal",
                                    _linhas(m.get("presc_obs"), 4), "CP, arts. 110, 112, 113, 116 e 117"))
    for k, kexp, rot, dec in DECRETOS:
        v = (m.get(k) or "").strip()
        if not v:
            continue
        txt = m.get(k + "_txt") or v
        if NAO_CABE.match(v):
            nao_cabe.append({"titulo": "%s · %s" % (rot, dec), "motivo": txt})
            continue
        if DECIDIDO.match(v) or DECIDIDO.match(txt):
            continue  # já decidido pelo juízo: não é ponto a conferir
        conta = _linhas(m.get(kexp) or m.get("det" + k[1:]), 8)
        if re.match(r"sim|poss", v, re.I):
            beneficios.append(_item(k, not sem_ficha, rot, "tempo atendido", "%s · %s" % (dec, txt),
                                    "falta grave no período do decreto (ficha disciplinar)" if sem_ficha else "", conta, dec))
        else:
            beneficios.append(_item(k, False, rot, "a verificar", "%s · %s" % (dec, txt),
                                    "o requisito indicado" + (" e a falta grave (ficha disciplinar)" if sem_ficha else ""), conta, dec))
    if m.get("st_ok") or m.get("st_quase"):
        pend = [x.get("txt") for x in m.get("st_itens") or [] if x.get("ok") is None]
        beneficios.append(_item("st", bool(m.get("st_ok")) and not pend, "Saída temporária",
                                "requisitos objetivos atendidos" if m.get("st_ok") else "quase atendidos", "",
                                "; ".join(pend) if pend else ("" if m.get("st_ok") else "requisitos objetivos ainda não atendidos"),
                                [x.get("txt") for x in m.get("st_itens") or []], "LEP, arts. 122 a 125"))

    if m.get("pa_ok") or m.get("pa_quase"):
        # progressão antecipada (ícone de degraus no APTO): critério do juízo, não de lei - sempre a conferir com o juízo
        pend = [x.get("txt") for x in m.get("pa_itens") or [] if x.get("ok") is None]
        beneficios.append(_item("pa", bool(m.get("pa_ok")) and not pend, "Progressão antecipada",
                                "requisitos atendidos" if m.get("pa_ok") else "a conferir", "",
                                "; ".join(pend) if pend else "",
                                [x.get("txt") for x in m.get("pa_itens") or []],
                                "LEP, art. 112; critério do juízo da execução para o pedido antes da data do SEEU"))

    # ---- demais pontos
    if sem_ficha and _custodiado(r, m):
        ult = _ultima_remicao(r)
        ref = ult or _inicio_custodia(r)
        if ref and (hoje - ref).days > SEM_ATESTADO_DIAS:
            demais.append(_item("atestado", False, "Atestado de trabalho ou estudo", "%d meses" % ((hoje - ref).days // 30),
                                ("última remição decidida em %s" % rs.fmt(ult)) if ult else ("sem remição decidida desde a prisão (%s)" % rs.fmt(ref)),
                                "pedir atestado à unidade prisional", [], "LEP, arts. 126 e 129"))
    rp_ = [x for x in m.get("rem_prio") or [] if x]
    if rp_:
        # remição pendente na ficha (dias exatos) que, declarada, já dá um benefício (ícone de avanço rápido no APTO)
        demais.append(_item("rem", False, "Remição pendente que já dá benefício", "", rp_[-1], "pedir a declaração da remição",
                            rp_[:-1], "LEP, arts. 126 a 129"))
    if not sem_ficha and (m.get("fd_cor") or "") in ("vermelho", "amarelo"):
        demais.append(_item("fd", False, "Ficha disciplinar: remição e atestados", "", m.get("fd_sit"), m.get("fd_sit") or "", [], "LEP, arts. 126 a 129"))
    recalc = []  # avisos que pedem o mesmo recálculo da progressão já decidida: um cartão só
    for i, a in enumerate(m.get("aud_itens") or []):
        if a.get("baixado") or a.get("nivel") not in ("alerta", "verificar"):
            continue
        if a.get("tipo") in RECALCULO_PROGRESSAO:
            recalc.append(a)
            continue
        demais.append(_item("aud%d" % i, False, a.get("titulo") or "", "", "", "conferir no cálculo do SEEU e nos autos",
                            _linhas(a.get("detalhe"), 4), a.get("fundamento") or ""))
    if len(recalc) == 1:
        a = recalc[0]
        demais.append(_item("recalc", False, a.get("titulo") or "", "", "", "conferir no cálculo do SEEU e nos autos",
                            _linhas(a.get("detalhe"), 4), a.get("fundamento") or ""))
    elif recalc:
        ref = next((a.get("ref") for a in recalc if a.get("ref")), "")
        motivos = [RECALCULO_PROGRESSAO[a["tipo"]] for a in recalc]
        fund = {}  # a mesma base citada nos dois avisos entra uma vez (a forma mais completa)
        for a in recalc:
            for f in re.split(r";\s*", (a.get("fundamento") or "").rstrip(".")):
                k = re.sub(r"\s*\(.*\)\s*$", "", f).strip()
                if k and len(f) > len(fund.get(k, "")):
                    fund[k] = f
        fund = list(fund.values())
        demais.append(_item("recalc", False, "Pedir o recálculo da progressão%s: %s lançadas depois dela" % (
                            (" de " + ref) if ref else "", " e ".join(motivos)),
                            "", "", "conferir no cálculo do SEEU e nos autos",
                            ["%d) %s" % (k + 1, a.get("detalhe") or "") for k, a in enumerate(recalc)], "; ".join(fund) + "."))

    # ficha disciplinar: a data de impressão (mais de 90 dias = conferir a atualizada) e a ficha oferecida que não é desta pessoa
    fic = m.get("ficha") if isinstance(m.get("ficha"), dict) else {}
    ficha_info = None
    if not sem_ficha:
        imp = rs.to_date(fic.get("data_impressao") or "")
        dias = (hoje - imp).days if imp else None
        ficha_info = {"nome": fic.get("nome") or "", "impressa": fic.get("data_impressao") or "", "dias": dias,
                      "velha": dias is None or dias > FICHA_VALIDADE_DIAS}
        if ficha_info["velha"]:
            demais.append(_item("ficha_velha", False, "Ficha disciplinar desatualizada", fic.get("data_impressao") or "sem data",
                                ("impressa há %s" % _extenso(dias)) if dias is not None else "sem a data de impressão",
                                "imprimir a ficha atual no SIAPEN: lançamentos posteriores (faltas, trabalho) não estão nesta", [], ""))
    elif fichas_n:
        demais.append(_item("ficha_outra", False, "Ficha disciplinar não usada", "", "a ficha carregada não confere com este assistido "
                            "(nome, mãe, CPF ou data de nascimento)", "carregar a ficha deste assistido", [], ""))
    for f in faltou or []:
        demais.append(_item("faltou", False, "Leitura incompleta", "", f, "conferir no SEEU: sem esse dado, o que depende dele fica a verificar"))

    crimes = [{"texto": "%s (%s)" % (x.get("nome_crime") or "Crime", x.get("dispositivo") or ""), "pena": x.get("pena") or "",
               "proc": x.get("proc") or "", "hediondo": x.get("hediondo_txt") or ""}
              for x in m.get("crimes_det") or [] if not re.match(r"^s", x.get("extinto") or "", re.I)]
    # ---- apresentação (v2.1, 11/2026): os marcos em linhas compactas (só a data e quanto falta; destaque quando está
    # próximo ou já foi atingido); o DESTAQUE fica com os alertas (tudo o que é para conferir, em cartões); o que confere
    # nos benefícios fica em linhas.
    linhas, alertas = [], []
    for x in marcos:
        d = rs.to_date(x["valor"] or "")
        n = (d - hoje).days if d else None
        quando = _quando(x["valor"], hoje) if x["id"] != "db" else ""
        extra = x["motivo"].replace(quando + "; ", "").replace(quando, "").strip("; ") if quando else x["motivo"]
        dest = ""
        if n is not None and x["id"] != "db":
            dest = "proximo" if 0 <= n <= PROXIMO_DIAS else ("atingida" if n < 0 and x["id"] in ("prog", "liv") else "")
        linhas.append({"id": x["id"], "rotulo": x["titulo"], "data": x["valor"], "quando": quando, "extra": extra, "destaque": dest,
                       "alerta": x["status"] == "amarelo", "conta": x["conta"], "fundamento": x["fundamento"]})
        if x["status"] == "amarelo":
            alertas.append(dict(x))
    confere = []
    for x in beneficios + demais:
        if x["status"] != "verde" and SEM_EFEITO.match(x["titulo"] or ""):
            observacoes.append(x)
        else:
            (confere if x["status"] == "verde" else alertas).append(x)
    cont = {"verde": len(confere) + sum(1 for x in linhas if not x["alerta"]), "amarelo": len(alertas)}
    # ícones dos benefícios (como os do APTO ao lado do nome), para os chips da página: cada um abre o seu cartão no painel
    icones = []
    for tipo, rot, ids in ICONES:
        its = [x for x in beneficios + demais if x["id"] in ids and x not in observacoes]
        if tipo == "presc":
            its = [x for x in its if x["status"] != "verde"]  # prescrição só quando aparente ou a verificar
        if not its:
            continue
        r0 = its[0]["titulo"] if tipo in ("ind", "com") else rot
        icones.append({"tipo": tipo, "rotulo": r0 + (" +%d" % (len(its) - 1) if len(its) > 1 else ""),
                       "estado": "ok" if any(x["status"] == "verde" for x in its) else "conferir", "alvo": its[0]["id"]})
    return {"processo": m.get("id") or r.get("processo_execucao") or "", "nome": m.get("nome") or r.get("nome") or "", "regime": reg,
            "hoje": rs.fmt(hoje), "pena": pena, "marcos": linhas, "alertas": alertas, "confere": confere, "crimes": crimes,
            "nao_cabe": nao_cabe, "observacoes": observacoes, "icones": icones, "contagem": cont, "ficha": not sem_ficha, "ficha_info": ficha_info}


_ULTIMO = {}  # processo (dígitos) -> (modelo do APTO, data de referência) da última análise nesta sessão do motor


def _assinar(p):
    return hashlib.sha1(json.dumps(p, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def analisar(r, sub=None, hoje=None, faltou=None, fichas_n=0):
    """Análise do painel: mesma entrada = mesmo resultado no APTO e na extensão. Devolve o painel com a versão do motor,
    a versão da base jurídica, a chave da entrada e a assinatura do resultado."""
    hoje = hoje or date.today()
    if isinstance(hoje, str):
        hoje = rs.to_date(hoje)
    sub = sub or copy.deepcopy(CTX_VAZIO)
    rv.HOJE = hoje
    chave = mt._chave_calculo(r, sub, hoje)
    m_bruto, _migrar = mt._montar_modelo(copy.deepcopy(r), copy.deepcopy(sub))  # o motor altera o que recebe: a entrada fica intacta
    _ULTIMO[re.sub(r"\D", "", r.get("processo_execucao") or "")] = (m_bruto, hoje)  # para o resumo do assistido, sem recalcular
    m = rv.json_seguro({k: v for k, v in m_bruto.items() if k != "_bruto"})
    p = montar(r, m, hoje, faltou, fichas_n)
    p["assinatura"] = _assinar(p)
    p.update({"chave": chave, "motor": mt.VERSAO, "painel": VERSAO_PAINEL, "base_juridica": rg.versao(), "base_digital": mt._bj_digital()})
    return p


def contexto_fichas(fichas):
    """Fatia do contexto com as fichas disciplinares oferecidas (carregadas no painel ou abertas no SIAPEN): cada uma pelo nome,
    como o APTO guarda a ficha ainda sem processo; o motor só a usa se for desta pessoa (mesmo nome e mãe, CPF, autos ou
    nascimento: rspe_motor._mesma_mae e _ficha_prova)."""
    sub = copy.deepcopy(CTX_VAZIO)
    for f in fichas or []:
        if isinstance(f, dict) and f.get("nome"):
            n = mt._norm(f["nome"])
            sub["fichas"]["nome:" + n] = f
            sub["homonimos"][n] = 1
    return sub


def analisar_abas(txt):
    """Painel a partir das ABAS do SEEU (sem o APTO): {"abas": {nome: HTML}, "hoje": "dd/mm/aaaa", "fichas": [ficha, ...]} em
    texto JSON -> painel em texto JSON. As abas viram o registro no formato do RSPE pelo leitor do APTO (rspe_seeu_abas); o que
    não foi achado nas abas vai em "faltou" e entra como ponto a conferir; as fichas oferecidas entram pelo contexto."""
    import rspe_seeu_abas as ra
    e = json.loads(txt)
    hoje = rs.to_date(e.get("hoje") or "") or date.today()
    r, faltou = ra.ler(e.get("abas") or {}, rs.fmt(hoje))
    if not r.get("processo_execucao"):
        return json.dumps({"erro": "sem_dados", "faltou": faltou, "diag": ra.diagnostico(e.get("abas"))}, ensure_ascii=False)
    fichas = [f for f in e.get("fichas") or [] if isinstance(f, dict)]
    p = analisar(r, contexto_fichas(fichas), hoje, faltou, len(fichas))
    if faltou:
        p["diag"] = ra.diagnostico(e.get("abas"))  # fora da assinatura: só para ajustar a leitura
    return json.dumps(p, ensure_ascii=False)


def analisar_rspe(txt):
    """Painel a partir do RSPE (Relatório da Situação Processual Executória) que o próprio SEEU gera para o processo aberto,
    lido no navegador: {"paginas": [caracteres do pdf.js] | "textos": [texto de cada página], "hash", "hoje", "fichas"} em texto
    JSON -> painel em texto JSON. É o MESMO caminho do APTO ao importar o RSPE: o texto de cada página como o pdfplumber o dá
    (rspe_pdf_paginas emula o extract_text) -> rspe_scraper.extrair_paginas -> o motor. O que o leitor não conseguiu ler
    ("_leitura_parcial") entra como ponto a conferir. Documento que não é o RSPE: {"erro": "nao_rspe", "motivo"}."""
    import rspe_pdf_paginas as pp
    e = json.loads(txt)
    hoje = rs.to_date(e.get("hoje") or "") or date.today()
    textos = e.get("textos")
    if textos is None:
        textos = [pg.extract_text() or "" for pg in pp.paginas(e.get("paginas") or [])]
    try:
        r = rs.extrair_paginas([str(t) for t in textos], "RSPE.pdf")
    except ValueError as x:
        return json.dumps({"erro": "nao_rspe", "motivo": str(x)}, ensure_ascii=False)
    if not r.get("processo_execucao"):
        return json.dumps({"erro": "nao_rspe", "motivo": "o relatório veio sem o número do processo"}, ensure_ascii=False)
    if e.get("hash"):
        r["_hash"] = str(e["hash"])
    fichas = [f for f in e.get("fichas") or [] if isinstance(f, dict)]
    return json.dumps(analisar(r, contexto_fichas(fichas), hoje, list(r.get("_leitura_parcial") or []), len(fichas)), ensure_ascii=False)


def ler_ficha(txt):
    """Ficha disciplinar do SIAPEN a partir dos caracteres que o pdf.js extraiu no navegador ({"paginas": [...], "arquivo"}):
    o MESMO leitor do APTO (rspe_ficha.extrair_paginas_pdf), sobre páginas no formato do pdfplumber (rspe_pdf_paginas).
    -> {"ficha": {...}, "resumo": {nome, mae, cpf, impressa}} ou {"erro": motivo}."""
    import rspe_ficha as rf
    import rspe_pdf_paginas as pp
    e = json.loads(txt)
    try:
        f = rf.extrair_paginas_pdf(pp.paginas(e.get("paginas")), e.get("arquivo") or "ficha.pdf")
    except ValueError as x:
        return json.dumps({"erro": str(x)}, ensure_ascii=False)
    return json.dumps({"ficha": rv.json_seguro(f), "resumo": {"nome": f.get("nome") or "", "mae": f.get("nome_mae") or "",
                                                              "cpf": f.get("cpf") or "", "impressa": f.get("data_impressao") or ""}},
                      ensure_ascii=False)


def resumo_assistido(txt):
    """Resumo para o assistido (linguagem simples, CNJ), como a janela do APTO o propõe (rspe_resumo.montar), a partir da última
    análise do processo nesta sessão: {"processo"} -> o texto proposto, para conferir e editar no painel. Sem a base do APTO, os
    pedidos já feitos não entram (a pessoa marca as providências). A unidade vem da ficha disciplinar, se houver."""
    import rspe_resumo as rres
    e = json.loads(txt)
    x = _ULTIMO.get(re.sub(r"\D", "", str(e.get("processo") or "")))
    if not x:
        return json.dumps({"erro": "sem_analise"})
    m, hoje = x
    d = rres.montar(m, {}, hoje, m.get("nome") or "")
    d["unidade"] = ((m.get("ficha") or {}).get("unidade") or "").strip() if isinstance(m.get("ficha"), dict) else ""
    return json.dumps(rv.json_seguro(d), ensure_ascii=False)


def resumo_pdf(txt, caminho="/tmp/resumo_assistido.pdf"):
    """PDF do resumo (o texto já conferido no painel), pelo MESMO gerador do APTO (rspe_relatorio.relatorio_resumo_assistido):
    {"d": resumo, "canhoto": bool} -> {"caminho", "canhoto", "verso"}. O canhoto (pedido do próximo atendimento) só vai no
    atendimento na unidade prisional - a pessoa escolhe no painel."""
    import rspe_relatorio as rrel
    e = json.loads(txt)
    d = dict(e.get("d") or {})
    d["canhoto"] = bool(e.get("canhoto"))
    rrel.relatorio_resumo_assistido(d, caminho)
    return json.dumps({"caminho": caminho, "canhoto": bool(d.get("_canhoto_saiu")), "verso": bool(d.get("_verso_saiu"))})
