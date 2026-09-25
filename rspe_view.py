# -*- coding: utf-8 -*-
"""
Modelo de exibição: transforma o registro extraído (rspe_scraper) nos campos
curtos que as abas, o Excel e o PDF mostram. Também define as abas/colunas.
"""

from datetime import date, datetime
from fractions import Fraction
import hashlib
import re

import rspe_scraper as rs
import rspe_prescricao as rp
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_regras as rg

HOJE = date.today()
# janelas de alerta (dias até o marco): acima da última, a situação fica em branco
ALERTAS_DIAS = [(30, "laranja"), (60, "amarelo"), (90, "verde")]

# cores (tom moderno): (fundo suave, texto forte)
CORES = {
    "vermelho": ("#FDE8E8", "#B42318"),
    "laranja": ("#FFEAD5", "#C4320A"),
    "amarelo": ("#FEF4D6", "#B54708"),
    "vencido": ("#FDE8E8", "#B42318"),
    "verde": ("#DDF5E7", "#067647"),
    "cinza": ("#EEF0F3", "#5B6470"),
    "azul": ("#DBEAFE", "#1D4ED8"),
    "": ("#FFFFFF", "#344054"),
}
ROTULO = {
    "lapso": {"vencido": "Vencido · verificar", "laranja": "Até 30 dias", "amarelo": "Até 60 dias", "verde": "Até 90 dias", "cinza": "Não se aplica / não iniciou / interrompida"},
    "indulto": {"verde": "Possível", "amarelo": "A verificar", "cinza": "Não atinge"},
    "presc": {"vermelho": "Prescrição aparente", "amarelo": "Iminente / a verificar", "": "Não prescrita", "cinza": "Sem dados"},
    "presc_pp": {"vermelho": "Prescrição aparente", "": "Não configurada", "cinza": "Sem dados"},
    "fd": {"vermelho": "Remição a requerer", "amarelo": "Conferir remição / ausência de atestado / último atestado há 6 meses", "verde": "Em ordem", "cinza": "Sem ficha"},
    "aud": {"vermelho": "Com alertas", "amarelo": "Pontos a verificar", "verde": "Sem inconsistências", "azul": "Extinta"},
    "ext": {"vermelho": "Extinção cabível", "laranja": "Término em até 30 dias", "amarelo": "Até 60 dias / a verificar", "verde": "Término em até 90 dias", "cinza": "Sem previsão / interrompida", "azul": "Extinta (registrada)"},
}

# filtros de situação por tipo de aba: (id, rótulo, função(modelo)->bool)
def _dias(m, k):
    return m.get(k)


FILTROS = {
    "fd": [
        ("todas", "Todas"),
        ("impeditivo", "Remição a requerer"),
        ("verificar", "Conferir remição / sem atestado / estudo"),
        ("ok", "Em ordem"),
        ("nao", "Sem ficha"),
    ],
    "lapso": [
        ("todas", "Todas"),
        ("vencidas", "Vencidas"),
        ("30", "Vence em até 30 dias"),
        ("60", "Vence em até 60 dias"),
        ("90", "Vence em até 90 dias"),
        ("naoiniciou", "Não iniciou o cumprimento"),
        ("interrompida", "Pena interrompida"),
        ("naoaplica", "Não se aplica (cumprida / livramento / aberto)"),
        ("semdata", "Sem data"),
    ],
    "indulto": [
        ("todas", "Todos os benefícios"),
        ("b:i25:Sim", "Indulto 2025 · Sim"), ("b:i25:Verificar", "Indulto 2025 · Verificar"),
        ("b:c25:Sim", "Comutação 2025 · Sim"), ("b:c25:Verificar", "Comutação 2025 · Verificar"),
        ("b:i24:Sim", "Indulto 2024 · Sim"), ("b:i24:Verificar", "Indulto 2024 · Verificar"),
        ("b:c24:Sim", "Comutação 2024 · Sim"), ("b:c24:Verificar", "Comutação 2024 · Verificar"),
        ("b:i22:Sim", "Indulto 2022 · Sim"), ("b:i22:Verificar", "Indulto 2022 · Verificar"),
        ("b:*:Fato posterior", "Fato posterior à data do decreto (qualquer benefício)"),
        ("b:*:Falta", "Falta nos 12 meses (qualquer benefício)"),
        ("impeditivo", "Crime impeditivo"),
    ],
    "ext": [
        ("todas", "Todas"),
        ("vencidas", "Extinção cabível"),
        ("30", "Término em até 30 dias"),
        ("60", "Término em até 60 dias"),
        ("90", "Término em até 90 dias"),
        ("interrompida", "Pena interrompida"),
        ("semdata", "Sem previsão"),
    ],
    "aud": [
        ("todas", "Todas"),
        ("atencao", "Com alertas"),
        ("verificar", "Pontos a verificar"),
        ("ok", "Sem inconsistências"),
    ],
    "presc": [
        ("todas", "Todas"),
        ("aparente", "Prescrição aparente"),
        ("iminente", "Prescrição iminente / a verificar"),
        ("naocorre", "Não prescrita / não configurada"),
        ("semdados", "Sem dados"),
        ("extinta", "Extinta"),
    ],
}


def _data(txt):
    return rs.to_date(txt) if txt else None


def _sem_data(r):
    """O programa não calcula progressão/livramento/término: sem data do SEEU, só informa o motivo."""
    if "INTERROMPIDA" in (r.get("situacao_cumprimento") or ""):
        return ("Pena interrompida", None)
    return ("Não consta no RSPE", None)


def execucao_extinta(r):
    """True se o RSPE registra a extinção da execução (incidente sem processo) ou todos os crimes extintos."""
    cr = r.get("_crimes", [])
    return bool(r.get("execucao_extinta")) or (bool(cr) and all(c.get("extinto", "").upper().startswith("S") for c in cr))


def nao_iniciou(r):
    """Não iniciou o cumprimento da pena: o RSPE não registra nenhum início de cumprimento definitivo - só prisões
    provisórias (flagrante, preventiva, temporária) já encerradas, ou nenhuma prisão."""
    evs = r.get("_eventos", [])
    inicios = [e for e in evs if re.search(r"PRIS|IN[ÍI]CIO|REIN[ÍI]CIO|RECAPTURA", ((e.get("tipo") or "") + " " + (e.get("motivo") or "")).upper())]
    definitivos = [e for e in inicios if not re.search(r"FLAGRANTE|PREVENTIV|TEMPOR|PROVIS", (e.get("motivo") or "").upper())]
    if definitivos:
        return False
    # sem prisão definitiva: só "não iniciou" se não está preso agora (a última prisão provisória foi encerrada)
    ordem = sorted(evs, key=lambda e: rs.to_date(e.get("data") or "") or date.min)
    if ordem and not re.search(r"INTERRUP", (ordem[-1].get("tipo") or "").upper()):
        return False
    # livramento, aberto com audiência/início registrado etc. não entram aqui
    if rs.livramento_em_curso(r, r.get("_incidentes", []))[0]:
        return False
    return True


def estado_execucao(r):
    """Estado que dispensa progressão/livramento: ('extinta', txt), ('cumprida', txt), ('lc', txt), ('aberto', txt) ou None."""
    if execucao_extinta(r):
        return ("extinta", "Pena extinta" + (" · " + r["execucao_extinta"] if r.get("execucao_extinta") else " (todos os crimes extintos)"))
    pt = rs.pena_para_dias(r.get("pena_total")) or 0
    rem = rs.pena_para_dias(r.get("pena_remanescente"))
    cump = rs.pena_para_dias(r.get("pena_cumprida"))
    term = rs.to_date(r.get("termino_previsao_seeu") or "")
    if pt and ((rem is not None and rem <= 0) or (cump is not None and cump >= pt) or (term and term <= HOJE)):
        return ("cumprida", "Pena cumprida" + (" em %s" % rs.fmt(term) if term else ""))
    regime = (r.get("regime_atual") or "").upper()
    lc, dl = rs.livramento_em_curso(r, r.get("_incidentes", []))
    if lc:
        duv = rs.duvidas_livramento(r, r.get("_eventos", []), r.get("_incidentes", []), dl)
        if duv and not r.get("_lc_confirmado"):
            return ("lc_duvida", "Livramento a confirmar" + (" (%s)" % rs.fmt(dl) if dl else "") + " · ver Auditoria")
        return ("lc", "Em livramento condicional" + (" desde %s" % rs.fmt(dl) if dl else ""))
    if nao_iniciou(r):
        return ("nao_iniciou", "Não iniciou o cumprimento")
    if regime.startswith("ABERTO"):
        m = rs.RE_DATA.search(r.get("progressao_obs_seeu") or "")
        return ("aberto", "Já em regime aberto" + (" (%s)" % m.group(1) if m else ""))
    return None


def data_progressao(r):
    est = estado_execucao(r)
    if est:
        return (est[1], None)
    if r.get("progressao_obs_seeu"):
        m = rs.RE_DATA.search(r["progressao_obs_seeu"])
        return ("Já em regime aberto" + (" (%s)" % m.group(1) if m else ""), None)
    if r.get("progressao_previsao_seeu"):
        return (r["progressao_previsao_seeu"], _data(r["progressao_previsao_seeu"]))
    return _sem_data(r)


def data_livramento(r):
    est = estado_execucao(r)
    if est and est[0] in ("extinta", "cumprida", "lc", "lc_duvida", "nao_iniciou"):
        return (est[1], None)
    # livramento deferido e depois suspenso/revogado: o RSPE responde pelos incidentes
    inc = r.get("_incidentes", [])
    dls = [rs.to_date(i.get("data_referencia") or i.get("data_decisao") or "") for i in inc if rs.e_concessao_livramento(i)]
    dls = [d for d in dls if d]
    if dls:
        dl = max(dls)
        fim = [(rs.to_date(i.get("data_referencia") or i.get("data_decisao") or ""), "revogado" if rs.e_revogacao_livramento(i) else "suspenso")
               for i in inc if rs.e_revogacao_livramento(i) or rs.e_suspensao_livramento(i)]
        fim = [x for x in fim if x[0] and x[0] > dl]
        if fim and not r.get("livramento_previsao_seeu"):
            d, t = max(fim)
            return ("Livramento %s em %s (deferido em %s)" % (t, rs.fmt(d), rs.fmt(dl)), None)
    pt = rs.pena_para_dias(r.get("pena_total"))
    _min = rg.carregar().get("livramento", {}).get("pena_minima_anos", 2)
    if pt and pt < _min * rs.DIAS_ANO and not r.get("livramento_previsao_seeu"):
        return ("Não cabível: pena < %s (art. 83 CP)" % rs.pl(_min, "ano", "anos"), None)
    if r.get("livramento_previsao_seeu"):
        return (r["livramento_previsao_seeu"], _data(r["livramento_previsao_seeu"]))
    return _sem_data(r)


VERIFICAR_VENCIDO = "verificar criminológico, indeferimento ou falta"


def situacao(d, interrompida=False):
    """(texto, cor)"""
    if d == "atingido":
        return ("Interrompida · lapso atingido", "cinza") if interrompida else ("Lapso atingido · " + VERIFICAR_VENCIDO, "vencido")
    if not d:
        return (("Pena interrompida", "cinza") if interrompida else ("", ""))
    n = (d - HOJE).days
    if n < 0:
        return ("Vencido há %d dia%s · %s" % (-n, "s" if n < -1 else "", VERIFICAR_VENCIDO), "vencido")
    if n == 0:
        return ("Vence hoje", "laranja")
    for lim, cor in ALERTAS_DIAS:
        if n <= lim:
            return ("Em %s" % rs.pl(n, "dia", "dias"), cor)
    return ("", "")  # acima de 90 dias: nada a fazer, nada a mostrar


def pedidos(r, palavra):
    inc = [i for i in r.get("_incidentes", []) if palavra in ("%s %s" % (i.get("tipo", ""), i.get("complemento", ""))).upper()]
    if not inc:
        return ""
    partes = []
    for sit, rot in (("NÃO CONCEDIDO", "negado"), ("PENDENTE", "pendente"), ("CONCEDIDO", "concedido")):
        xs = [i for i in inc if i.get("situacao") == sit]
        if xs:
            ult = max((i.get("data_decisao") or i.get("data_referencia") or "" for i in xs),
                      key=lambda s: _data(s) or date.min)
            partes.append("%s %dx (últ. %s)" % (rot, len(xs), ult) if len(xs) > 1 else "%s (%s)" % (rot, ult))
    return "; ".join(partes)


def curto_indulto(txt):
    if not txt:
        return ""
    falta = " · falta 12m!" if "FALTA nos 12 meses" in txt else (" · falta a verificar" if "falta a verificar (art. 6º" in txt else "")
    base = txt.split(" | ")[0]
    if "fato posterior" in txt and "fato posterior" not in base:
        # o resultado vale para as penas anteriores; a do fato posterior segue em execução
        falta += " · fato posterior segue"
    if base.startswith("VEDAD"):
        return "Vedado (art. 1º)"
    if base.startswith("NÃO CABE (art. 6º)"):
        return "Não cabe · falta grave 12m (art. 6º)"
    m = rs.re.match(r"POSSÍVEL \((.+?)\): (.*)$", base)
    if m:
        q = m.group(1)
        rot = "Possível"
        extra = " · só crimes não impeditivos (art. 7º, p. ú.)" if "art. 7º" in q else ""
        extra += " · tese: hed. superveniente" if "hediondez" in q else ""
        return "%s · %s%s%s" % (rot, m.group(2).replace("art. 9º, ", ""), extra, falta)
    if base.startswith("POSSÍVEL"):
        return base.replace("POSSÍVEL: ", "Possível · ").split("; § 5º")[0].replace("art. 5º (todos os crimes com pena máxima ≤ 5 anos)", "art. 5º (pena máx. ≤ 5 anos)") + falta
    if base.startswith("A VERIFICAR"):
        m = rs.re.match(r"A VERIFICAR(?: \((.+?)\))?: (.*)$", base)
        if m:
            extra = " · só crimes não impeditivos (art. 7º, p. ú.)" if (m.group(1) and "art. 7º" in m.group(1)) else ""
            extra += " · tese: hed. superveniente" if (m.group(1) and "hediondez" in m.group(1)) else ""
            return "A verificar · %s%s%s" % (m.group(2), extra, falta)
        return base.replace("A VERIFICAR: ", "A verificar · ") + falta
    if base.startswith("não se aplica: sem condenação"):
        # a data é a do decreto: falta ou prisão posterior não contradiz (o que conta é a condenação até ali)
        md = rs.re.search(r"até (\d{2}/\d{2}/\d{4})", base)
        return "Não se aplica (sem condenação até %s)" % md.group(1) if md else "Não se aplica (sem condenação na data)"
    if base.startswith("não se aplica: fatos") or "fato posterior" in base:
        return "Não se aplica (fatos posteriores)"
    if base.startswith(("não se aplica: não iniciou", "não se aplica: cumprimento interrompido")):
        # a data deixa claro que a situação é a da data do decreto (faltas posteriores não contradizem)
        md = rs.re.search(r"até (\d{2}/\d{2}/\d{4})", base)
        oque = "não iniciou o cumprimento" if "não iniciou" in base else "cumprimento interrompido"
        return "Não se aplica (%s em %s)" % (oque, md.group(1)) if md else "Não se aplica (%s)" % oque
    if base.startswith("não se aplica: sem pena em cumprimento"):
        md = rs.re.search(r"em (\d{2}/\d{2}/\d{4})", base)
        return "Não se aplica (sem pena em cumprimento em %s)" % md.group(1) if md else "Não se aplica (sem execução na data)"
    if base.startswith("não se aplica"):
        return "Não se aplica (sem execução na data)"
    if base.startswith("CONCEDIDO no RSPE"):
        return "Concedido · " + base.split(" em ")[-1]
    if base.startswith("INDEFERIDO no RSPE"):
        return "Indeferido · " + base.split(" em ")[-1]
    if base.startswith("prejudicada"):
        return "Prejudicada · indulto cabível"
    if base.startswith("excluído"):
        return "Excluído (art. 7º)"
    if base.startswith("não atinge: pena dos crimes impeditivos"):
        return "Não atinge · pena dos crimes impeditivos não cumprida (art. 11, p. ú.)" + falta
    m = rs.re.search(r"cumprido (\S+) de ([0-9amd]+)", base)
    if m:
        return "Não atinge (%s de %s)" % (m.group(1), m.group(2)) + falta
    if base.startswith("não atinge"):
        return "Não atinge" + falta
    return base + falta


def cor_texto_indulto(txt):
    t = (txt or "").split(" | ")[0]
    if t.startswith("CONCEDIDO no RSPE"):
        return "azul"
    if t.startswith("VEDAD"):
        return "vermelho"
    if t.startswith("POSSÍVEL"):
        return "verde"
    if t.startswith("A VERIFICAR"):
        return "amarelo"
    return "cinza"


def curto_impeditivo(r):
    if r.get("indulto_crime_impeditivo") != "SIM":
        return "Não"
    det = r.get("indulto_crime_impeditivo_detalhe", "")
    partes = [p.split(":")[0].replace("art. 1º, ", "") + " · " + p.split(":")[1].strip().split(" (")[0]
              for p in det.split("; ") if ":" in p]
    sup = " (hediondez posterior ao fato)" if "fato anterior" in det else ""
    return "Sim · art. 1º, " + "; ".join(partes) + sup


def compacto_indulto(txt):
    """Versão curta para a célula da tabela; o texto completo vai para o tooltip e para a ficha."""
    t = txt or ""
    t = rs.re.sub(r"\s*\((?:sem execução na data|fatos posteriores|sem condenação até [\d/]+|sem pena em cumprimento em [\d/]+|não iniciou o cumprimento em [\d/]+|cumprimento interrompido em [\d/]+)\)", "", t)
    t = t.replace("Vedado (art. 1º)", "Vedado · art. 1º").replace("Excluído (art. 7º)", "Excluído · art. 7º")
    t = t.replace(" · art. 9º, ", " · ").replace("art. 5º (pena máx. ≤ 5 anos)", "art. 5º")
    t = rs.re.sub(r"^Não atinge \(.*\)$", "Não atinge", t)
    t = rs.re.sub(r"^não atinge.*$", "Não atinge", t)
    t = rs.re.sub(r"^Possível · art\. 13 \([^)]*\)", "Possível · art. 13", t)
    t = t.replace(" · tese: hed. superveniente", " · tese hed. superv.")
    t = t.replace(" · só crimes não impeditivos (art. 7º, p. ú.)", " · não impeditivos")
    t = rs.re.sub(r"^(A verificar · art\. 7º, p\. ú\.).*$", r"\1 (2/3 do impeditivo)", t)
    return t


def compacto_impeditivo(txt):
    if not txt.startswith("Sim"):
        return txt
    corpo = txt[len("Sim · art. 1º, "):] if txt.startswith("Sim · art. 1º, ") else ""
    incs = [p.split(" · ")[0].strip() for p in corpo.split("; ") if p.strip()]
    sup = " · hed. superveniente" if "posterior ao fato" in txt else ""
    return ("Sim · art. 1º, " + "; ".join(incs) if incs else "Sim") + sup


def cor_indulto(r):
    if execucao_extinta(r):
        return "azul"
    st = {r.get("indulto_2022_status"), r.get("indulto_2024_status"), r.get("indulto_2025_status")}
    if "possivel" in st:
        return "verde"  # mesmo com crime impeditivo: art. 7º, p. ú., ou tese da hediondez superveniente
    if r.get("indulto_crime_impeditivo") == "SIM":
        return "vermelho"
    if "verificar" in st or "POSSÍVEL" in (r.get("comutacao_2025", "") + r.get("comutacao_2024", "")):
        return "amarelo"
    return "cinza"


def termino(r):
    if r.get("termino_previsao_seeu"):
        return r["termino_previsao_seeu"]
    if nao_iniciou(r):
        return "Não iniciou"
    return "Interrompida" if "INTERROMPIDA" in (r.get("situacao_cumprimento") or "") else "Não consta no RSPE"


def extincao(r, presc, interr):
    """Hipóteses de extinção da pena/punibilidade aferíveis pelo RSPE."""
    hip, cor, d_ref = [], "", None
    pt = rs.pena_para_dias(r.get("pena_total")) or 0
    cump = rs.pena_para_dias(r.get("pena_cumprida"))
    term = rs.to_date(r.get("termino_previsao_seeu") or "")
    # 1) pena cumprida
    if pt and cump is not None and cump >= pt:
        hip.append("Pena integralmente cumprida (%s de %s): extinção pelo cumprimento (LEP, art. 66, II)" % (rs.dias_para_pena(cump), rs.dias_para_pena(pt)))
        cor, d_ref = "vermelho", HOJE
    elif term and term <= HOJE:
        hip.append("Término da pena previsto para %s já alcançado" % rs.fmt(term))
        cor, d_ref = "vermelho", term
    # 2) livramento condicional: período de prova expirado sem revogação
    inc = r.get("_incidentes", [])
    _lc_ok, _ = rs.livramento_em_curso(r, inc)
    lcs = [i for i in inc if rs.e_concessao_livramento(i)] if _lc_ok else []
    if lcs:
        dlc = max((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "") or date.min for i in lcs))
        revog = any(rs.e_revogacao_livramento(j) and (rs.to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.min) > dlc for j in inc)
        duv = rs.duvidas_livramento(r, r.get("_eventos", []), inc, dlc if dlc != date.min else None) if not revog else []
        # livramento com situação incerta: fica só na Auditoria (esta aba mostra apenas extinção pelo cumprimento)
        if dlc != date.min and not revog and duv:
            pass
        elif dlc != date.min and not revog and term:
            if term <= HOJE:
                hip.append("Livramento condicional desde %s com período de prova expirado em %s sem revogação (CP, arts. 89 e 90; LEP, art. 146)" % (rs.fmt(dlc), rs.fmt(term)))
                cor = "vermelho"
    # 3) detração que alcança toda a pena do processo (custódia provisória anterior ao trânsito): hipótese a verificar,
    #    porque a mesma prisão pode servir a várias condenações (LEP, art. 111). Prescrição e indulto ficam nas próprias abas.
    a_verificar = False
    for l in presc.get("presc_linhas", []):
        if l.get("ppe_detracao_cobre"):
            hip.append("%s: a verificar - custódia anterior ao trânsito de %s iguala ou supera a pena do processo (%s); se computada nesta "
                       "condenação, extinção pelo cumprimento (CP, art. 42; LEP, arts. 66, II, e 111)" % (l.get("rotulo") or l["crime"], rs.dias_para_pena(l.get("ppe_detracao_dias") or 0), l.get("ppe_pena_processo") or l["pena"]))
            a_verificar = True
    # multa cominada: extinção exige prova da impossibilidade de pagamento (STF ADI 7.032)
    com_multa = any(re.search(r"\b(E|e)\s+Multa", c.get("tipo_penal") or "") for c in r.get("_crimes", []) if not c.get("extinto", "").upper().startswith("S"))
    multa_txt = ("Multa cominada: extinção cabível se comprovada a impossibilidade de pagamento (STF ADI 7.032, vinculante; STJ Tema 931) - instruir com prova da hipossuficiência" if com_multa else "")
    # crimes já extintos no RSPE
    ext = ["%s%s%s" % (rs.crimes_curto([c]).replace(" (extinto)", ""), (" · " + c["extincao_motivo"].lower()) if c.get("extincao_motivo") else "",
                       (" em " + c["data_extincao"]) if c.get("data_extincao") else "")
           for c in r.get("_crimes", []) if c.get("extinto", "").upper().startswith("S")]
    todos_extintos = bool(r.get("_crimes")) and all(c.get("extinto", "").upper().startswith("S") for c in r.get("_crimes", []))
    if r.get("execucao_extinta") or todos_extintos:
        hip.insert(0, "Execução já extinta segundo o RSPE (%s)" % (r.get("execucao_extinta") or "todos os crimes extintos"))
        cor = "extinta"
    # prazo do término (livramento com situação incerta fica só na Auditoria)
    ja_extinta = cor == "extinta"
    if ja_extinta:
        cor = "azul"
    elif cor != "vermelho":
        if interr and not term:
            cor = "cinza"
        elif term:
            n = (term - HOJE).days
            cor = next((c for lim, c in ALERTAS_DIAS if n <= lim), "")
        else:
            cor = "cinza"
        if a_verificar and cor in ("", "cinza", "verde"):
            cor = "amarelo"
    return {
        "ext_hipoteses": "; ".join(hip) if hip else ("Não iniciou o cumprimento - sem previsão" if nao_iniciou(r) else ("" if not interr else "Pena interrompida - sem previsão")),
        "ext_cor": cor,
        "ext_termino": rs.fmt(term) if term else ("Não iniciou" if nao_iniciou(r) else ("Interrompida" if interr else "")),
        "ext_dias": (term - HOJE).days if term else None,
        "ext_sit": ("Pena extinta (registrada)" if ja_extinta else (("Extinção cabível" if cor == "vermelho" else situacao(term)[0].replace("Vence", "Término").replace("Em ", "Término em ")) if (term or cor == "vermelho") else "")),
        "ext_extintos": "; ".join(ext),
        "ext_multa": multa_txt,
        "ext_n": len(hip),
    }


def _vencido_full(r, sit, cor, palavra):
    """Dica (tooltip) do prazo vencido: o que o RSPE mostra sobre pedidos, exame criminológico e faltas."""
    if cor != "vencido":
        return sit
    partes = [sit]
    ped = pedidos(r, palavra)
    partes.append("Pedidos no RSPE: " + ped if ped else "Nenhum pedido registrado no RSPE")
    crim = [i for i in r.get("_incidentes", []) if "CRIMINOL" in ("%s %s" % (i.get("tipo", ""), i.get("complemento", ""))).upper()]
    if crim:
        partes.append("Exame criminológico: " + "; ".join("%s (%s)" % (i.get("situacao", "").lower(), i.get("data_decisao") or i.get("data_referencia") or "") for i in crim))
        if palavra == "PROGRESS":
            fatos = sorted(set(c.get("data_infracao") for c in r.get("_crimes", []) if c.get("data_infracao") and not c.get("extinto", "").upper().startswith("S")),
                           key=lambda x: rs.to_date(x) or date.min)
            partes.append("A verificar: exame exigido só pela Lei 14.843/2024 (LEP, art. 112, § 1º) não alcança fato anterior à vigência dela "
                          "(STJ, HC 950.729 e AgRg no HC 974.282; STF, Tema 1408: repercussão geral reconhecida no RE 1.536.743, 13/06/2025 - conferir se já houve julgamento)%s" % ((" - fatos de " + ", ".join(fatos)) if fatos else ""))
    if r.get("falta_12m") == "SIM":
        partes.append("Falta nos últimos 12 meses: " + (r.get("falta_12m_detalhe") or "sim"))
    elif r.get("falta_12m") == "A APURAR":
        partes.append("Falta a apurar nos últimos 12 meses (sem sanção reconhecida no RSPE): " + (r.get("falta_12m_detalhe") or ""))
    return " · ".join(partes)


def _dias_para(d):
    if d == "atingido":
        return 0
    if isinstance(d, date):
        return (d - HOJE).days
    return None


# pontos que outras abas já mostram (indulto e comutação, prescrição, prazos vencidos, extinção, início do
# cumprimento): o filtro é pelo tipo do ponto, não por palavra do título (uma extinção cujo motivo cita a prescrição
# continua na Auditoria)
AUD_OUTRAS_ABAS = {
    "indulto-possivel-sem-incidente-no-rspe", "comutacao-possivel-sem-incidente-no-rspe", "indulto-hipoteses-a-verificar",
    "hediondez-posterior-ao-fato-indulto-comutacao-po", "violencia-domestica-confirmar-se-a-vitima-e-mulh",
    "prescricao-da-pretensao-executoria-aparente", "prescricao-da-pretensao-punitiva-aparente",
    "prescricao-nao-aferivel-por-completo-datas-ausen", "menor-de-21-anos-no-fato-prescricao-pela-metade",
    "vencida-em-sem-decisao-posterior-no-rspe", "nao-iniciou-o-cumprimento-da-pena", "cumprimento-interrompido-ultimo-evento-e-interru",
    "transito-em-julgado-nao-informado", "pena-cumprida-por-detracao", "prescricao-executoria-a-verificar-saldo-na-evasao",
    "livramento-condicional-com-pena-total-inferior-a",
}
# idade (LEP 117, I; § 2º dos decretos) e multa (ADI 7.032) ficam na Auditoria: nenhuma outra aba os mostra


def so_matematica(it):
    """Itens que ficam na Auditoria: conferência dos números e datas do RSPE."""
    if it.get("origem") == "ficha":
        return it["titulo"].startswith("Perda de remidos")  # perda de dias remidos é conta do RSPE
    return it.get("tipo") not in AUD_OUTRAS_ABAS


# ---------------- telas simplificadas: data ou "—"; Sim/Não/Verificar; o motivo vai para a ficha ----------------
TRACO = "—"


def so_data(txt):
    """Coluna de data: a data do SEEU, "Pena extinta" / "Pena cumprida", ou "—" (o motivo fica na ficha)."""
    t = (txt or "").strip()
    if re.match(r"^\d{2}/\d{2}/\d{4}", t):
        return t
    if t.startswith("Pena extinta"):
        return "Pena extinta"
    if t.startswith("Pena cumprida"):
        return "Pena cumprida"
    return TRACO


def sim_nao(txt, cor):
    """Indulto/comutação na tela: Sim, Não, Verificar (Concedido quando o RSPE já registra)."""
    t = txt or ""
    if cor == "azul" or t.startswith("Concedido"):
        return "Concedido", "azul"
    if cor in ("verde", "amarelo") and "falta 12m" in t:
        # art. 6º: falta grave com sanção reconhecida nos 12 meses anteriores a 25/12 impede a declaração (detalhe na ficha)
        return "Falta", "vermelho"
    if cor == "verde" and "falta a verificar" in t:
        # falta pendente, regressão ou perda de remidos sem falta datada: só impede se a sanção for reconhecida
        return "Verificar", "amarelo"
    if cor == "verde":
        return "Sim", "verde"  # possível, ainda que por tese (a tese aparece no texto e no cálculo)
    if cor == "amarelo":
        return "Verificar", "amarelo"
    if not t:
        return "", ""
    # o "Não" diz o motivo: fato posterior, vedado pelo decreto ou não atinge (inclui "não se aplica")
    if ("fato posterior" in t and "fato posterior segue" not in t) or "fatos posteriores" in t:
        # só quando não resta crime anterior alcançável
        return "Fato posterior", "cinza"
    if t.startswith("Não cabe") and "falta" in t:
        return "Falta", "vermelho"  # art. 6º: falta grave nos 12 meses (inclui fuga) - o motivo fica na ficha
    if t.startswith("Vedado"):
        return "Vedado (art. 1º)", "vermelho"
    if t.startswith("Excluído"):
        return "Vedado (art. 7º)", "vermelho"
    if t.startswith("Indeferido"):
        return "Indeferido", "vermelho"
    if t.startswith("Prejudicada"):
        return "Prejudicada", "cinza"
    if t.startswith("Não se aplica (sem condenação"):
        return "Não se aplica", "cinza"  # nenhuma condenação na publicação do decreto (o motivo fica na ficha)
    return "Não atinge", "cinza"


def presc_curto(txt, ppe=False):
    t = (txt or "").strip()
    tl = t.lower()
    if not t:
        return ""
    if tl.startswith("aparente") or "aparente" in tl[:40]:
        return "Aparente"
    if tl.startswith("iminente"):
        return "Iminente"
    if tl.startswith("a verificar"):
        return "A verificar"
    if "extint" in tl:
        return "Extinta"
    if tl.startswith("não configurada"):
        return "Não configurada"
    if tl.startswith("não prescrita") or tl.startswith("não corre") or tl.startswith("pena cumprida"):
        return "Não prescrita"
    if tl.startswith("verificar") or "sem pena" in tl or "sem dados" in tl:
        return "Sem dados"
    return "Não prescrita" if ppe else "Não configurada"


def simplificar(m):
    m["prog_motivo"], m["liv_motivo"], m["termino_motivo"] = m.get("prog", ""), m.get("liv", ""), m.get("termino", "")
    m["prog"], m["liv"], m["termino"] = so_data(m["prog"]), so_data(m["liv"]), so_data(m["termino"])
    m["ext_termino_motivo"] = m.get("ext_termino", "")
    m["ext_termino"] = so_data(m.get("ext_termino", "")) if m.get("ext_termino") else TRACO
    for k in ("prog", "liv"):
        sit, cor = m.get(k + "_sit", ""), m.get(k + "_cor", "")
        if cor == "cinza" and not sit.startswith("Pena cumprida"):
            m[k + "_sit_full"] = m.get(k + "_sit_full") or sit
            m[k + "_sit"] = "Não se aplica"
    for k in ("prog", "liv"):
        if not m.get(k + "_sit") and re.match(r"^\d{2}/\d{2}/\d{4}", m.get(k) or ""):
            m[k + "_sit"] = "Em cumprimento"
    if re.search(r"sem previsão\s*$", m.get("ext_hipoteses") or ""):
        m["ext_motivo"], m["ext_hipoteses"] = m["ext_hipoteses"], TRACO
    if not m.get("ext_sit"):
        if re.match(r"^\d{2}/\d{2}/\d{4}", m.get("ext_termino") or ""):
            m["ext_sit"] = "Em cumprimento"
        elif m.get("ext_cor") == "cinza":
            m["ext_sit"] = "Não se aplica"
    # indulto e comutação
    m["imp_curto"] = "Sim" if (m.get("imp") or "").startswith("Sim") else ("Não" if m.get("imp") else "")
    for k in ("i22", "i24", "c24", "i25", "c25"):
        m[k + "_txt"] = m.get(k + "_full") or m.get(k, "")
        m[k + "_cor_rel"] = m.get(k + "_cor", "")  # cor do relatório em PDF (o vermelho da aba é só para a tela)
        m[k], m[k + "_cor"] = sim_nao(m[k + "_txt"], m.get(k + "_cor", ""))
        if m[k] == "Falta":
            m[k + "_cor_rel"] = "vermelho"  # art. 6º: o relatório acompanha a tela
        elif m[k] == "Verificar" and m[k + "_cor_rel"] == "verde":
            m[k + "_cor_rel"] = "amarelo"  # falta a verificar (art. 6º)
    m["imp_txt"], m["imp"] = m.get("imp_full") or m.get("imp", ""), m["imp_curto"]
    m["imp_cor"] = "vermelho" if m["imp_curto"] == "Sim" else ("verde" if m["imp_curto"] == "Não" else "")
    m["ind_sim"] = any(m.get(k + "_cor") == "verde" for k in ("i22", "i24", "c24", "i25", "c25"))
    if m.get("ind_cor") == "verde" and not m["ind_sim"]:
        # o único "possível" ficou barrado pela falta do art. 6º
        m["ind_cor"] = "vermelho" if m.get("imp_curto") == "Sim" else ("amarelo" if any(m.get(k + "_cor") == "amarelo" for k in ("i22", "i24", "c24", "i25", "c25")) else "cinza")
    # prescrição
    m["presc_retro_full"], m["presc_ppe_full"] = m.get("presc_retro", ""), m.get("presc_ppe", "")
    m["presc_retro"], m["presc_ppe"] = presc_curto(m["presc_retro_full"]), presc_curto(m["presc_ppe_full"], ppe=True)
    m["presc_retro"] = m["presc_retro"] or "Sem dados"
    m["presc_ppe"] = m["presc_ppe"] or "Sem dados"
    _pc = {"Aparente": "vermelho", "Iminente": "amarelo", "A verificar": "amarelo", "Extinta": "azul", "Sem dados": "cinza"}
    m["presc_retro_cor"], m["presc_ppe_cor"] = _pc.get(m["presc_retro"], ""), _pc.get(m["presc_ppe"], "")
    return m


def chave_item(it):
    """Chave da baixa: tipo do ponto + crime/ano/falta (estável quando o título muda por números ou agrupamento).
    Item sem tipo (ficha disciplinar) usa o título, como antes."""
    if it.get("tipo"):
        return "t:" + hashlib.sha1(("%s|%s" % (it["tipo"], it.get("ref") or "")).encode("utf-8")).hexdigest()[:12]
    return hashlib.sha1(it["titulo"].encode("utf-8")).hexdigest()[:12]


def baixa_de(it, baixas):
    """(baixa, chave antiga a migrar). Baixas gravadas até a 6.15.11 usam o sha1 do título."""
    b = baixas.get(chave_item(it))
    if b:
        return b, ""
    antiga = hashlib.sha1(it["titulo"].encode("utf-8")).hexdigest()[:12]
    if antiga != chave_item(it) and antiga in baixas:
        return baixas[antiga], antiga
    return None, ""


def modelo(r, baixas=None, ficha=None, manuais=None, extras=None):
    """Registro extraído -> dict plano com tudo que as abas mostram. baixas: {chave: {obs, data}} da auditoria.
    ficha: Ficha Disciplinar do SIAPEN já lida (rspe_ficha.extrair), se houver. extras: itens da Auditoria criados
    fora da análise (falha ao ler a ficha), que entram na contagem, na cor e no resumo."""
    baixas = baixas or {}
    r = dict(r)
    # baixa dada pelo usuário no alerta de livramento incerto = livramento confirmado (vale em todas as abas, inclusive
    # no indulto: a análise dos decretos é refeita sem a ressalva "livramento a confirmar")
    _lc, _dl = rs.livramento_em_curso(r, r.get("_incidentes", []))
    if _lc:
        _t = "Livramento condicional%s com situação incerta no RSPE" % ((" deferido em %s" % rs.fmt(_dl)) if _dl else "")
        if baixa_de({"titulo": _t, "tipo": "livramento-condicional-com-situacao-incerta-no-r"}, baixas)[0]:
            r["_lc_confirmado"] = True
            try:
                # refaz os três decretos antes de reaplicar as decisões do RSPE (sem isso, a de 2022 seria aplicada duas vezes)
                r.update(rs.analise_decretos(r, r.get("_crimes", []), r.get("_eventos", []), r.get("_incidentes", []), None))
                r.update(rs.analise_decreto_2022(r, r.get("_crimes", []), r.get("_eventos", []), r.get("_incidentes", [])))
                rs.aplicar_decisoes_decretos(r, r.get("_incidentes", []))
            except Exception:
                pass
    if ficha:
        try:
            rf.complementar_decretos(r, ficha, HOJE)  # XI, XII e XIII do art. 9º pela ficha (saídas, trabalho externo, estudo, curso)
        except Exception:
            pass
    sem_inicio = nao_iniciou(r)
    interr = "INTERROMPIDA" in (r.get("situacao_cumprimento") or "") and not sem_inicio
    ptxt, pd = data_progressao(r)
    ltxt, ld = data_livramento(r)
    est = estado_execucao(r)
    psit, pcor = situacao(pd, interr)
    lsit, lcor = situacao(ld, interr)
    if est:
        psit, pcor = ({"extinta": "Pena extinta", "cumprida": "Pena cumprida", "lc": "Em livramento", "aberto": "Já no aberto", "lc_duvida": "A verificar (livramento)",
                       "nao_iniciou": "Não iniciou o cumprimento"}[est[0]],
                      "amarelo" if est[0] == "lc_duvida" else "azul" if est[0] == "extinta" else "cinza")
        if est[0] in ("extinta", "cumprida", "lc", "lc_duvida", "nao_iniciou"):
            lsit, lcor = (psit, pcor)
    presc = rp.analisar(r, HOJE)
    aud = ra.auditar(r, HOJE)
    ext = extincao(r, presc, interr)
    if execucao_extinta(r):
        presc["presc_cor"] = "azul"
        presc["presc_retro"] = presc["presc_retro"] or "Extinta"
        presc["presc_ppe"] = "Pena extinta (registrada no RSPE)"
    if ficha:
        try:
            aud["aud_itens"] = rf.confrontar(r, ficha, HOJE) + aud["aud_itens"]
        except Exception as e:
            aud["aud_itens"].insert(0, {"nivel": "verificar", "titulo": "Ficha disciplinar: falha ao confrontar (%s)" % e, "detalhe": "", "fundamento": "",
                                        "tipo": "falha-confronto", "ref": ""})
    # a Auditoria cuida da matemática do RSPE; o que já aparece nas outras abas (remição/ficha, indulto e
    # comutação, prescrição, prazos vencidos, extinção) não se repete aqui
    aud["aud_itens"] = list(extras or []) + [i for i in aud["aud_itens"] if so_matematica(i)]
    aud["aud_itens"].sort(key=lambda i: {"alerta": 0, "verificar": 1, "info": 2, "ok": 3}.get(i["nivel"], 9))
    for it in aud["aud_itens"]:
        it["chave"] = chave_item(it)
        b, antiga = baixa_de(it, baixas)
        if not b and it.get("auto_baixa"):
            b = it["auto_baixa"]  # dado preenchido: o alerta aparece como baixado, com a origem do dado
        if antiga:
            it["migrar_de"] = antiga  # o app regrava a baixa na chave nova
        it["baixado"] = bool(b)
        if b:
            it["baixa_obs"], it["baixa_data"] = b.get("obs", ""), b.get("data", "")
            it["nivel_cor"], it["nivel_txt"] = "cinza", "Baixado"
        else:
            it["nivel_cor"] = {"alerta": "vermelho", "verificar": "amarelo", "ok": "verde", "info": "cinza"}[it["nivel"]]
            it["nivel_txt"] = {"alerta": "Alerta", "verificar": "Verificar", "ok": "OK", "info": "Info"}[it["nivel"]]
    # recontagem sem os baixados
    n_al = sum(1 for i in aud["aud_itens"] if i["nivel"] == "alerta" and not i["baixado"])
    n_ve = sum(1 for i in aud["aud_itens"] if i["nivel"] == "verificar" and not i["baixado"])
    n_bx = sum(1 for i in aud["aud_itens"] if i["baixado"])
    n_info = sum(1 for i in aud["aud_itens"] if i["nivel"] == "info" and not i["baixado"])
    aud["aud_alertas"], aud["aud_verificar"] = n_al, n_ve
    aud["aud_status"] = "atencao" if n_al else ("verificar" if n_ve else "ok")
    pl = lambda n, s1, s2: "%d %s" % (n, s1 if n == 1 else s2)
    partes = []
    if n_al:
        partes.append(pl(n_al, "alerta", "alertas"))
    if n_ve:
        partes.append(pl(n_ve, "ponto a verificar", "pontos a verificar"))
    aud["aud_resumo"] = " · ".join(partes) if partes else "Sem inconsistências"
    if n_bx:
        aud["aud_resumo"] += " · " + pl(n_bx, "baixado", "baixados")
    aud["aud_info"] = n_info
    # coluna Falta: "Sim" só com sanção reconhecida; indício sem ela, "A apurar" (o detalhe fica na ficha do assistido)
    falta = (("Sim · " + (r.get("falta_12m_detalhe") or "")) if r.get("falta_12m") == "SIM" else
             "A apurar" if r.get("falta_12m") == "A APURAR" else "Não consta")
    m = {
        "id": r.get("processo_execucao") or r.get("arquivo"),
        "nome": nome_proprio(r.get("nome", "")),
        "proc": r.get("processo_execucao", ""),
        "geral_cor": "azul" if execucao_extinta(r) else "",
        "regime": ("Livramento condicional" if (est and est[0] == "lc") else
                   ("Livramento? (RSPE: %s)" % (r.get("regime_atual") or "").replace(" - ATIVO", "") if (est and est[0] == "lc_duvida") else
                    ((r.get("regime_atual") or "").replace(" - ATIVO", "") + (" (não iniciado)" if (est and est[0] == "nao_iniciou" and r.get("regime_atual")) else "")))),
        "regime_rspe": (r.get("regime_atual") or "").replace(" - ATIVO", ""),
        "vara": r.get("vara", ""),
        "crimes": rs.crimes_curto(r.get("_crimes", [])) or r.get("crimes_curto") or "",
        "termino": termino(r),
        "prog": ptxt, "prog_sit": psit, "prog_cor": pcor, "prog_dias": _dias_para(pd),
        "prog_sit_full": _vencido_full(r, psit, pcor, "PROGRESS"), "liv_sit_full": _vencido_full(r, lsit, lcor, "LIVRAMENTO"),
        "liv_dias": _dias_para(ld), "interrompida": interr, "estado_exec": est[0] if est else "",
        "presc_cor": presc["presc_cor"], "presc_retro": presc["presc_retro"], "presc_ppe": presc["presc_ppe"],
        "presc_prox": presc["presc_prox"], "presc_dias": presc["presc_dias"], "presc_obs": presc["presc_obs"],
        "presc_linhas": presc["presc_linhas"], "presc_n": len(presc["presc_linhas"]),
        "ind_status": [r.get("indulto_2022_status", ""), r.get("indulto_2024_status", ""), r.get("indulto_2025_status", "")],
        **ext,
        **rf.comparativo(r, ficha, HOJE, conferidos={k for k in baixas if k.startswith("fd:")}, manuais=manuais),
        "ficha_resumo": rf.resumo(ficha) if ficha else "",
        "conduta_ruim": bool(ficha and re.search(r"RESPONDE|REGULAR|\bM[ÁA]\b|P[ÉE]SSIMA|RUIM", (ficha.get("conduta") or "").upper())),
        "conduta": ((ficha.get("conduta") or "não informada na ficha").title().replace("Padic", "PADIC").replace("Ipcg", "IPCG").replace("Otima", "Ótima").replace("Pessima", "Péssima") if ficha else "Sem ficha"),
        "ficha_tem": bool(ficha),
        "ficha": ({k: ficha.get(k) for k in ("nome", "rgi", "cpf", "unidade", "data_entrada", "data_prisao", "conduta", "data_impressao", "trabalho", "atestados",
                                             "dias_trabalhados_atestados", "dias_remidos_atestados", "faltas", "regressoes", "restabelecimentos", "recusa_trabalho", "isolamentos", "estudo", "autos", "importado_em")}
                  if ficha else None),
        "aud_info": aud.get("aud_info", 0),
        "aud_cor": "azul" if execucao_extinta(r) else {"atencao": "vermelho", "verificar": "amarelo", "ok": "verde"}[aud["aud_status"]],
        "aud_status": aud["aud_status"], "aud_resumo": aud["aud_resumo"], "aud_alertas": aud["aud_alertas"],
        "aud_verificar": aud["aud_verificar"], "aud_itens": aud["aud_itens"], "aud_n": len(aud["aud_itens"]),
        "aud_base": aud["aud_base"],
        "frac_prog": rs.pct(r.get("fracao_progressao_aplicada", "")),
        "dbase": r.get("data_base_seeu") or r.get("data_base", ""),
        "ped_prog": pedidos(r, "PROGRESS"),
        "liv": ltxt, "liv_sit": lsit, "liv_cor": lcor,
        "frac_liv": r.get("fracao_livramento_aplicada", ""),
        "ped_liv": pedidos(r, "LIVRAMENTO"),
        "falta": falta,
        "falta_sim": r.get("falta_12m") == "SIM",
        "falta_apurar": r.get("falta_12m") == "A APURAR",
        "falta_full": ("A apurar · " + (r.get("falta_12m_detalhe") or "")) if r.get("falta_12m") == "A APURAR" else falta,
        "falta_det": r.get("falta_12m_detalhe") or "",
        "imp": compacto_impeditivo(curto_impeditivo(r)), "imp_full": curto_impeditivo(r),
        "i22": compacto_indulto(curto_indulto(r.get("indulto_2022", ""))), "i22_full": curto_indulto(r.get("indulto_2022", "")),
        "i22_cor": cor_texto_indulto(r.get("indulto_2022", "")),
        "det22": r.get("indulto_2022_detalhe", ""),
        "ind22": r.get("indulto_2022", ""),
        "i24": compacto_indulto(curto_indulto(r.get("indulto_2024", ""))), "i24_full": curto_indulto(r.get("indulto_2024", "")),
        "i25": compacto_indulto(curto_indulto(r.get("indulto_2025", ""))), "i25_full": curto_indulto(r.get("indulto_2025", "")),
        "c24": compacto_indulto(curto_indulto(r.get("comutacao_2024", ""))), "c24_full": curto_indulto(r.get("comutacao_2024", "")),
        "c24_cor": cor_texto_indulto(r.get("comutacao_2024", "")),
        "c25": compacto_indulto(curto_indulto(r.get("comutacao_2025", ""))), "c25_full": curto_indulto(r.get("comutacao_2025", "")),
        "ind_cor": cor_indulto(r),
        "i24_cor": cor_texto_indulto(r.get("indulto_2024", "")),
        "i25_cor": cor_texto_indulto(r.get("indulto_2025", "")),
        "c25_cor": cor_texto_indulto(r.get("comutacao_2025", "")),
        "det24": r.get("indulto_2024_detalhe", ""),
        "cdet24": r.get("comutacao_2024_detalhe", ""), "cdet25": r.get("comutacao_2025_detalhe", ""),
        "exp22": r.get("indulto_2022_explica", ""), "exp24": r.get("indulto_2024_explica", ""), "exp25": r.get("indulto_2025_explica", ""),
        "cexp24": r.get("comutacao_2024_explica", ""), "cexp25": r.get("comutacao_2025_explica", ""),
        "det25": r.get("indulto_2025_detalhe", ""),
        "geracao": r.get("data_geracao_rspe", ""),
        "importado": r.get("importado_em", ""),
        "arquivo": r.get("arquivo", ""),
        "pena_total": rs.pena_extenso(r.get("pena_total", "")),
        "pena_cumprida": rs.pena_extenso(r.get("pena_cumprida", "")),
        "pena_rem": rs.pena_extenso(r.get("pena_remanescente", "")),
        "remidos": r.get("saldo_remidos", ""),
        "cumprimento": r.get("situacao_cumprimento", ""),
        "imp_det": r.get("indulto_crime_impeditivo_detalhe", ""),
        "ind24": r.get("indulto_2024", ""), "ind25": r.get("indulto_2025", ""),
        "com24": r.get("comutacao_2024", ""), "com25": r.get("comutacao_2025", ""),
        "ind_rspe": r.get("indulto_comutacao_incidentes", ""),
        "historico": r.get("historico_regime", ""),
        "eventos": r.get("eventos", ""),
        "crimes_det": [
            {"nome_crime": rs.nome_crime(c), "dispositivo": rs.dispositivo(c), "lei": rs.lei_curta(c.get("lei")), "artigo": ("art. " + rs.num_art(c.get("artigo")) + ((" " + rs.paragrafo_texto(c)) if rs.paragrafo_texto(c) else "")) if rs.num_art(c.get("artigo")) else "", "extinto": c.get("extinto", ""),
             "pena": rs.pena_extenso(c.get("pena_imposta")), "fato": c.get("data_infracao"),
             "vga": c.get("vga"), "morte": c.get("resultado_morte"), "reinc": "%s/%s" % (c.get("reincidente_comum"), c.get("reincidente_especifico")),
             "hediondo": c.get("hediondo_ou_equiparado"), "proc": c.get("processo_criminal"), "desc": c.get("tipo_penal"),
             "frac_prog": rs.pct_rotulo(c.get("fracao_progressao")), "frac_liv": c.get("fracao_livramento")}
            for c in r.get("_crimes", [])],
        "incidentes": [
            {"sit": i.get("situacao"), "tipo": i.get("tipo"), "comp": i.get("complemento"),
             "dec": i.get("data_decisao"), "ref": i.get("data_referencia")}
            for i in r.get("_incidentes", []) if not i.get("_ficha")],
    }
    m["motivo_exec"] = est[1] if est else ("Pena interrompida" if interr else "")
    return simplificar(m)


def item_falha(titulo, tipo="falha"):
    it = {"nivel": "alerta", "titulo": titulo, "detalhe": "Conferir o PDF: um dado ilegível impediu parte da análise.", "fundamento": "",
          "tipo": tipo, "ref": "", "baixado": False, "nivel_cor": "vermelho", "nivel_txt": "Alerta"}
    it["chave"] = chave_item(it)
    return it


def modelo_erro(r, erro, baixas=None):
    """Registro que não pôde ser analisado: aparece em todas as abas com o aviso, sem derrubar a base."""
    it = item_falha("Falha ao analisar este RSPE (%s)" % erro, "falha-analise")
    b, antiga = baixa_de(it, baixas or {})
    if antiga:
        it["migrar_de"] = antiga
    if b:
        it.update(baixado=True, baixa_obs=b.get("obs", ""), baixa_data=b.get("data", ""), nivel_cor="cinza", nivel_txt="Baixado")
    m = {k: "" for a in ABAS for k, _, _ in a["cols"]}
    for a in ABAS:
        for k in list(a["pilulas"].values()) + [a["cor"]]:
            m[k] = ""
    m.update({"id": r.get("processo_execucao") or r.get("arquivo"), "nome": nome_proprio(r.get("nome", "")), "proc": r.get("processo_execucao", ""),
              "regime": (r.get("regime_atual") or "").replace(" - ATIVO", ""), "aud_itens": [it], "aud_n": 1, "aud_alertas": 0 if b else 1, "aud_verificar": 0,
              "aud_status": "ok" if b else "atencao", "aud_cor": "verde" if b else "vermelho",
              "aud_resumo": "Falha ao analisar (baixada) - conferir o PDF" if b else "Falha ao analisar - conferir o PDF", "aud_base": "base jurídica %s" % rg.versao(),
              "aud_info": 0, "presc_linhas": [], "presc_n": 0, "fd_linhas": [], "fd_blocos": [], "ind_status": [], "crimes_det": [], "incidentes": [],
              "ficha_tem": False, "ficha": None, "falta_sim": False, "falta_apurar": False, "falta_det": "", "interrompida": False, "estado_exec": "", "ind_sim": False,
              "arquivo": r.get("arquivo", ""), "geracao": r.get("data_geracao_rspe", ""), "erro": str(erro)})
    return m


# abas: colunas (chave, título, peso), campo de cor, campo "status" (pílula), tipo de legenda
PRESC_SUB = [("crime", "Crime", 12), ("proc_crim", "Ação penal", 15), ("pena", "Pena", 7), ("fato", "Fato", 9), ("denuncia", "R. Denúncia", 9), ("sentenca", "Sentença", 9),
             ("transito", "Trânsito", 9), ("prazo_ppp", "Prazo PPP", 9), ("retro_status", "Retroativa / intercorrente", 20),
             ("prazo_ppe", "Prazo PPE", 11), ("ppe_termo", "Termo inicial", 9), ("ppe_status", "Executória", 22)]
ABAS = [
    {"id": "geral", "titulo": "Geral", "cor": "geral_cor", "legenda": "lapso", "sem_stats": True,
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 17), ("regime", "Regime", 9),
              ("prog", "Progressão", 15), ("liv", "Livramento", 15), ("termino", "Término", 10)],
     "pilulas": {}},
    {"id": "prog", "titulo": "Progressão", "cor": "prog_cor", "legenda": "lapso",
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 18), ("regime", "Regime", 9),
              ("prog", "Data da progressão", 14), ("prog_sit", "Situação", 16), ("conduta", "Conduta (ficha)", 12), ("falta", "Falta (12 meses)", 14)],
     "pilulas": {"prog_sit": "prog_cor"}},
    {"id": "liv", "titulo": "Livramento", "cor": "liv_cor", "legenda": "lapso",
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 18),
              ("liv", "Data do livramento", 14), ("liv_sit", "Situação", 16), ("conduta", "Conduta (ficha)", 12), ("falta", "Falta (12 meses)", 14)],
     "pilulas": {"liv_sit": "liv_cor"}},
    {"id": "ind", "titulo": "Indulto / Comutação", "cor": "ind_cor", "legenda": "indulto",
     "cols": [("nome", "Nome", 16), ("proc", "Nº da execução", 14),
              ("imp", "Impeditivo (art. 1º)", 10),
              ("i22", "Indulto 2022", 10), ("i24", "Indulto 2024", 10), ("c24", "Comutação 2024", 10), ("i25", "Indulto 2025", 10), ("c25", "Comutação 2025", 10)],
     "pilulas": {"imp": "imp_cor", "i22": "i22_cor", "i24": "i24_cor", "c24": "c24_cor", "i25": "i25_cor", "c25": "c25_cor"}},
    {"id": "presc", "titulo": "Prescrição", "cor": "presc_cor", "legenda": "presc", "expansivel": True,
     "cols": [("nome", "Nome", 20), ("proc", "Nº da execução", 17),
              ("presc_retro", "Pretensão punitiva", 14), ("presc_ppe", "Pretensão executória", 14), ("presc_prox", "Prescrição em", 10)],
     "pilulas": {"presc_retro": "presc_retro_cor", "presc_ppe": "presc_ppe_cor"},
     "sub": "presc_linhas", "sub_cols": PRESC_SUB, "sub_pilulas": {"retro_status": "retro_cor", "ppe_status": "ppe_cor"}, "sub_calc": True},
    {"id": "ext", "titulo": "Extinção", "cor": "ext_cor", "legenda": "ext",
     "cols": [("nome", "Nome", 20), ("proc", "Nº da execução", 17),
              ("ext_termino", "Término", 12), ("ext_sit", "Situação", 20)],
     "pilulas": {"ext_sit": "ext_cor"}},
    {"id": "fd", "titulo": "Ficha disciplinar", "cor": "fd_cor", "legenda": "fd", "expansivel": True,
     "cols": [("nome", "Nome", 20), ("proc", "Nº da execução", 15), ("fd_trab", "Trabalho atual", 18),
              ("fd_atestar", "Trabalho a atestar", 10), ("fd_estudo", "Estudo a requerer", 10), ("fd_sit", "Situação", 20)],
     "pilulas": {"fd_sit": "fd_cor"},
     "sub": "fd_linhas", "sub_cols": [("emp", "Emprego / estudo", 14), ("un", "Unidade", 8), ("per", "Período", 14), ("dias", "Dias", 6), ("at", "Atestado / horas", 26), ("sit", "Situação / providência", 28)],
     "sub_pilulas": {"sit": "cor"}},
    {"id": "aud", "titulo": "Auditoria", "cor": "aud_cor", "legenda": "aud", "expansivel": True,
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 17),
              ("aud_resumo", "Resultado da auditoria", 40)],
     "pilulas": {"aud_resumo": "aud_cor"},
     "sub": "aud_itens", "sub_cols": [("nivel_txt", "Nível", 9), ("titulo", "Ponto auditado", 26), ("detalhe", "O que foi encontrado", 40), ("fundamento", "Fundamento", 24)],
     "sub_pilulas": {"nivel_txt": "nivel_cor"}, "sub_calc": False, "sub_baixa": True},
]
ABA_POR_ID = {a["id"]: a for a in ABAS}
ABAS_PEDIDO = ("prog", "liv", "ind", "presc", "ext", "fd")
for _a in ABAS:
    # a aba Geral não tem prazo próprio (não há campo de dias): sem filtro de situação
    _a["filtros"] = [] if _a["id"] == "geral" else list(FILTROS.get(_a["id"], FILTROS["indulto"] if _a["id"] == "ind" else FILTROS["lapso"]))
    if _a["id"] in ABAS_PEDIDO:
        # controle de pedidos: coluna "Pedido" (feito em dd/mm/aaaa ou botão para marcar) e filtro
        _a["cols"] = list(_a["cols"]) + [("pedido", "Pedido", 9)]
        _a["filtros"] += [("pedfeito", "Pedido já feito"), ("pedsem", "Sem pedido")]
    _a["campo_dias"] = {"prog": "prog_dias", "liv": "liv_dias", "presc": "presc_dias", "ext": "ext_dias"}.get(_a["id"], "")


_PARTICULAS = {"da", "de", "do", "das", "dos", "e", "di", "du", "del", "della", "van", "von", "y"}
_ROMANOS = re.compile(r"^(i{1,3}|iv|v|vi{1,3}|ix|x)$", re.I)


def nome_proprio(nome):
    """Nome no padrão de nome próprio, qualquer que seja a grafia do SEEU (caixa alta ou mista):
    'RODRIGO DEUSDEDIT DA SILVA' -> 'Rodrigo Deusdedit da Silva'; 'Caua De Paula Alves' -> 'Caua de Paula Alves'.
    Partículas (da, de, do, das, dos, e) em minúscula; algarismos romanos em maiúscula (Neto II);
    D'Ávila, Sant'Ana e nomes compostos com hífen mantêm a maiúscula em cada parte. Só muda a exibição:
    a base guarda o nome como veio do SEEU."""
    def parte(w):
        return "'".join(x[:1].upper() + x[1:] for x in w.split("'")) if "'" in w else w[:1].upper() + w[1:]
    out = []
    for i, w in enumerate(re.sub(r"\s+", " ", (nome or "").strip()).split(" ")):
        if not w:
            continue
        lw = w.lower()
        if i > 0 and lw in _PARTICULAS:
            out.append(lw)
        elif i > 0 and _ROMANOS.match(lw):
            out.append(lw.upper())
        else:
            out.append("-".join(parte(x) for x in lw.split("-")))
    return " ".join(out)


def json_seguro(o):
    """Cópia do modelo que a tela consegue receber: Fraction vira número, date vira dd/mm/aaaa, tupla/conjunto vira lista.
    (A ponte com a tela serializa em JSON; um Fraction perdido derrubava a lista inteira.)"""
    if isinstance(o, dict):
        return {k: json_seguro(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [json_seguro(v) for v in o]
    if isinstance(o, Fraction):
        return int(o) if o.denominator == 1 else float(o)
    if isinstance(o, (date, datetime)):
        return o.strftime("%d/%m/%Y")
    return o
