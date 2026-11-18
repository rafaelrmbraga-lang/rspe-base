# -*- coding: utf-8 -*-
"""Painel do APTO na página do processo do SEEU: a análise de UM assistido, pronta para mostrar.

O MESMO código roda no APTO (servidor local, para conferir) e na extensão (Pyodide, no navegador): a entrada é o registro
no formato do RSPE (o que as abas do SEEU dão, ou o RSPE lido pelo APTO), a fatia do contexto da base (ficha, ajustes
manuais; vazia sem o APTO) e a data de referência. O cálculo é o do APTO (rspe_motor._montar_modelo), sem nenhuma conta
nova; aqui só se escolhe o que mostrar, em que ordem e com que nível da escala de situação do APTO:
  crit (◆ agir já) · urg (▲ até 30 dias) · med (● a conferir) · prox (○ até 90 dias) · ok (✓ cabe) · info (■ registrado) · neutro (—).

Regras do painel (decisões de 11/2026):
- o que depende da ficha disciplinar (falta grave, trabalho, comportamento) sai "a conferir" quando a ficha não está na
  análise, dizendo o quê e onde conferir; nunca "cabe" sem a ficha;
- só se pede conferência do que era possível (o motor já afasta, por exemplo, a hipótese de saídas temporárias de quem
  estava no fechado na data do decreto);
- custodiado sem remição decidida há mais de 6 meses: "a conferir: pedir atestado de trabalho ou estudo à unidade".
A assinatura do resultado (sha1 do painel) e a chave da entrada (rspe_motor._chave_calculo) permitem ao APTO e à extensão
conferirem que deram o mesmo resultado para a mesma entrada."""
import copy
import hashlib
import json
import re
from datetime import date

import rspe_motor as mt
import rspe_regras as rg
import rspe_scraper as rs
import rspe_view as rv

VERSAO_PAINEL = 1
SEM_ATESTADO_DIAS = 180  # 6 meses sem remição decidida, custodiado: pedir atestado

CTX_VAZIO = {"baixas": {}, "fichas": {}, "manuais": {}, "ajustes": {}, "dmanuais": {}, "peds": {}, "hist_n": {}, "fixados": {},
             "homonimos": {}, "outras_cond": {}, "outros_procs": {}, "outras_exec": {}, "homon_det": {}}

# cor do APTO -> nível da escala de situação
COR_NIVEL = {"vencido": "crit", "vermelho": "crit", "laranja": "urg", "amarelo": "med", "verde": "ok", "azul": "info", "cinza": "neutro"}
GRUPOS = [("crit", "Agir já"), ("urg", "Até 30 dias"), ("med", "A conferir"), ("prox", "Até 90 dias"), ("ok", "Cabe"),
          ("info", "Registrado"), ("neutro", "Em acompanhamento")]
ORDEM = {g: i for i, (g, _) in enumerate(GRUPOS)}

DECRETOS = [("i25", "exp25", "Indulto 2025", "Decreto 12.790/2025"), ("c25", "cexp25", "Comutação 2025", "Decreto 12.790/2025"),
            ("i24", "exp24", "Indulto 2024", "Decreto 12.338/2024"), ("c24", "cexp24", "Comutação 2024", "Decreto 12.338/2024"),
            ("i22", "exp22", "Indulto 2022", "Decreto 11.302/2022")]
NAO_CABE = re.compile(r"^(vedad|n[aã]o atinge|fato posterior|prejudicad|n[aã]o se aplica|falta|n[aã]o cab)", re.I)
PROXIMO = {"fechado": "semiaberto", "semiaberto": "aberto"}


def _nivel_cor(cor, dias=None):
    n = COR_NIVEL.get((cor or "").strip().lower())
    if n:
        return n
    if isinstance(dias, int):
        if dias < 0:
            return "crit"
        if dias <= 30:
            return "urg"
        if dias <= 90:
            return "prox"
    return "neutro"


def _linhas(txt, n=8):
    return [x.strip() for x in str(txt or "").split("\n") if x.strip()][:n]


def _item(id_, nivel, titulo, data="", linha="", conferir="", conta=None, fundamento=""):
    return {"id": id_, "nivel": nivel, "titulo": titulo, "data": data or "", "linha": linha or "", "conferir": conferir or "",
            "conta": [c for c in (conta or []) if c], "fundamento": fundamento or ""}


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


def montar(r, m, hoje):
    """Painel a partir do registro (r) e do modelo do APTO (m, já em json_seguro)."""
    itens, nao_cabe = [], []
    sem_ficha = _sem_ficha(m)
    reg = (m.get("regime") or "").strip()
    reg_l = rs._sem_acento(reg).lower()

    # ---- progressão
    ps = m.get("prog_sit") or ""
    if m.get("prog") and m.get("prog") != "—" and not re.match(r"(n[aã]o se aplica|pena cumprida|pena interrompida)", ps, re.I):
        prox = next((v for k, v in PROXIMO.items() if k in reg_l), "")
        nv = _nivel_cor(m.get("prog_cor"), m.get("prog_dias"))
        conf = "comportamento carcerário (ficha disciplinar)" if sem_ficha and nv in ("crit", "urg", "prox") else ""
        itens.append(_item("prog", nv, "Progressão ao " + prox if prox else "Progressão de regime", m.get("prog"), ps, conf,
                           ["Data-base: %s" % m["dbase"] if m.get("dbase") else "", "Fração: %s" % m["frac_prog"] if m.get("frac_prog") else "",
                            "Pena cumprida: %s" % m["pena_cumprida"] if m.get("pena_cumprida") else "",
                            "Pena a cumprir: %s" % m["pena_rem"] if m.get("pena_rem") else ""], "LEP, art. 112"))

    # ---- livramento condicional
    ls = m.get("liv_sit") or ""
    if re.match(r"vedad|n[aã]o cab", ls, re.I):
        nao_cabe.append({"titulo": "Livramento condicional", "motivo": ls})
    elif m.get("liv") and m.get("liv") != "—" and not re.match(r"(n[aã]o se aplica|pena cumprida|pena interrompida|pena suspensa)", ls, re.I):
        nv = _nivel_cor(m.get("liv_cor"), m.get("liv_dias"))
        conf = "comportamento satisfatório e falta grave nos últimos 12 meses (ficha disciplinar)" if sem_ficha and nv in ("crit", "urg", "prox") else ""
        itens.append(_item("liv", nv, "Livramento condicional", m.get("liv"), ls, conf,
                           ["Fração: %s" % m["frac_liv"] if m.get("frac_liv") else "", m.get("liv_motivo") if m.get("liv_motivo") != m.get("liv") else ""],
                           "CP, art. 83"))

    # ---- extinção / término
    es = m.get("ext_sit") or ""
    if re.match(r"extin[cç][aã]o cab|extin[cç][aã]o a verificar|t[eé]rmino em", es, re.I):
        itens.append(_item("ext", _nivel_cor(m.get("ext_cor"), m.get("ext_dias")), "Extinção da pena", m.get("ext_termino") or m.get("termino"), es,
                           "", [m.get("ext_termino_motivo") if m.get("ext_termino_motivo") != m.get("ext_termino") else ""], "CP, art. 82; LEP, art. 146"))

    # ---- prescrição executória
    pp = m.get("presc_ppe") or ""
    if re.match(r"aparente|iminente|a verificar", pp, re.I):
        nv = {"aparente": "crit", "iminente": "urg"}.get(pp.lower().split()[0], "med")
        itens.append(_item("presc", nv, "Prescrição executória " + pp.lower(), m.get("presc_prox"), m.get("presc_ppe_full") or pp,
                           "" if nv != "med" else "datas e marcos interruptivos na aba Prescrição do APTO",
                           _linhas(m.get("presc_obs"), 4), "CP, arts. 110, 112, 113, 116 e 117"))

    # ---- indulto e comutação
    for k, kexp, rot, dec in DECRETOS:
        v = (m.get(k) or "").strip()
        if not v:
            continue
        txt = m.get(k + "_txt") or v
        if NAO_CABE.match(v):
            nao_cabe.append({"titulo": "%s · %s" % (rot, dec), "motivo": txt})
            continue
        conta = _linhas(m.get(kexp) or m.get("det" + k[1:]), 8)
        if re.match(r"sim|poss", v, re.I):
            if sem_ficha:
                itens.append(_item(k, "med", "%s · %s" % (rot, dec), "tempo ok", txt,
                                   "falta grave no período do decreto (ficha disciplinar)", conta, dec))
            else:
                itens.append(_item(k, "ok", "%s · %s" % (rot, dec), "cabe", txt, "", conta, dec))
        else:  # "Verificar"
            itens.append(_item(k, "med", "%s · %s" % (rot, dec), "a conferir", txt,
                               "o ponto indicado no texto" + (" e a falta grave (ficha disciplinar)" if sem_ficha else ""), conta, dec))

    # ---- saída temporária (só quem está no semiaberto)
    if m.get("st_ok") or m.get("st_quase"):
        pend = [x.get("txt") for x in m.get("st_itens") or [] if x.get("ok") is None]
        itens.append(_item("st", "med" if pend else ("ok" if m.get("st_ok") else "prox"), "Saída temporária",
                           "", "requisitos objetivos atendidos" if m.get("st_ok") else "requisitos objetivos quase atendidos",
                           "; ".join(pend), [x.get(("txt")) for x in m.get("st_itens") or []], "LEP, arts. 122 a 125"))

    # ---- ficha disciplinar (com ficha: o que a aba Ficha do APTO aponta)
    if not sem_ficha and COR_NIVEL.get(m.get("fd_cor") or "") in ("crit", "med"):
        itens.append(_item("fd", COR_NIVEL[m["fd_cor"]], "Ficha disciplinar: remição e atestados", "", m.get("fd_sit"), "", [], "LEP, arts. 126 a 129"))

    # ---- atestado de trabalho ou estudo (sem a ficha: pelo que o SEEU mostra)
    if sem_ficha and _custodiado(r, m):
        ult = _ultima_remicao(r)
        ref = ult or _inicio_custodia(r)
        if ref and (hoje - ref).days > SEM_ATESTADO_DIAS:
            meses = (hoje - ref).days // 30
            itens.append(_item("atestado", "med", "Atestado de trabalho ou estudo", "%d meses" % meses,
                               ("Última remição decidida em %s" % rs.fmt(ult)) if ult else ("Sem remição decidida desde a prisão (%s)" % rs.fmt(ref)),
                               "pedir atestado à unidade prisional", [], "LEP, arts. 126 e 129"))

    # ---- auditoria do cálculo do SEEU
    for i, a in enumerate(m.get("aud_itens") or []):
        if a.get("baixado") or a.get("nivel") not in ("alerta", "verificar"):
            continue
        itens.append(_item("aud%d" % i, "crit" if a["nivel"] == "alerta" else "med", a.get("titulo") or "", "",
                           "", "" if a["nivel"] == "alerta" else "conferir no RSPE e nos autos", _linhas(a.get("detalhe"), 4),
                           a.get("fundamento") or ""))

    itens.sort(key=lambda x: ORDEM.get(x["nivel"], 99))  # sort estável: dentro do nível, a ordem acima
    grupos = [{"nivel": g, "rotulo": rot, "itens": [x for x in itens if x["nivel"] == g]} for g, rot in GRUPOS]
    grupos = [g for g in grupos if g["itens"]]
    prazos = [
        {"rotulo": "Término · SEEU", "valor": r.get("termino_previsao_seeu") or "—", "sub": "previsão do SEEU"},
        {"rotulo": "Término · APTO", "valor": m.get("termino") or "—", "sub": "com remição: " + (m.get("remidos") or "0 dias").split(" (")[0]},
        {"rotulo": "Prescrição executória", "valor": pp or "—", "sub": ("próximo marco " + m["presc_prox"]) if m.get("presc_prox") else ""},
        {"rotulo": "Pena cumprida", "valor": m.get("pena_cumprida") or "—", "sub": "de " + (m.get("pena_total") or "—")},
    ]
    cont = {n: sum(1 for x in itens if x["nivel"] == n) for n in ("crit", "urg", "med")}
    return {"processo": m.get("id") or r.get("processo_execucao") or "", "nome": m.get("nome") or r.get("nome") or "", "regime": reg,
            "hoje": rs.fmt(hoje), "grupos": grupos, "nao_cabe": nao_cabe, "prazos": prazos, "contagem": cont,
            "ficha": not sem_ficha}


def _assinar(p):
    return hashlib.sha1(json.dumps(p, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def analisar(r, sub=None, hoje=None):
    """Análise do painel: mesma entrada = mesmo resultado no APTO e na extensão. Devolve o painel com a versão do motor,
    a versão da base jurídica, a chave da entrada e a assinatura do resultado."""
    hoje = hoje or date.today()
    if isinstance(hoje, str):
        hoje = rs.to_date(hoje)
    sub = sub or copy.deepcopy(CTX_VAZIO)
    rv.HOJE = hoje
    chave = mt._chave_calculo(r, sub, hoje)
    m, _migrar = mt._montar_modelo(copy.deepcopy(r), copy.deepcopy(sub))  # o motor altera o que recebe: a entrada fica intacta
    m = rv.json_seguro({k: v for k, v in m.items() if k != "_bruto"})
    p = montar(r, m, hoje)
    p["assinatura"] = _assinar(p)
    p.update({"chave": chave, "motor": mt.VERSAO, "painel": VERSAO_PAINEL, "base_juridica": rg.versao(), "base_digital": mt._bj_digital()})
    return p


def usar_base(b):
    """Base jurídica que o APTO aberto está usando de fato (a cópia editável ao lado do APTO.exe pode ser mais nova que a
    embutida): a extensão calcula com ela, para o resultado bater. Sem APTO, vale a embutida no pacote do motor."""
    if not isinstance(b, dict) or not b:
        return False
    if rg._BASE is b:
        return True
    rg._BASE, rg._ORIGEM, rg._AVISOS = b, "APTO aberto", []
    mt._BJ_DIG[0] = None  # a impressão digital da base é refeita
    return True


def analisar_json(txt):
    """Entrada e saída em texto JSON (a ponte com o JavaScript da extensão):
    {"r": registro, "sub": fatia do contexto, "hoje": "dd/mm/aaaa", "base_juridica": base em uso no APTO (opcional)}."""
    e = json.loads(txt)
    if e.get("base_juridica"):
        usar_base(e["base_juridica"])
    return json.dumps(analisar(e["r"], e.get("sub"), e.get("hoje")), ensure_ascii=False)


def analisar_dossie(txt):
    """O dossiê do APTO (POST /painel/dossie), em TEXTO, como chegou: a extensão não o relê em JavaScript antes (o JSON.parse
    do navegador troca 5.0 por 5 e muda a impressão digital da entrada). Devolve o painel calculado aqui, em JSON."""
    d = json.loads(txt)
    usar_base(d.get("base_juridica"))
    return json.dumps(analisar(d["r"], d.get("sub"), d.get("hoje")), ensure_ascii=False)
