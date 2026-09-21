# -*- coding: utf-8 -*-
"""
Modelo de exibição: transforma o registro extraído (rspe_scraper) nos campos
curtos que as abas, o Excel e o PDF mostram. Também define as abas/colunas.
"""

from datetime import date
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
    "vencido": ("#FEF4D6", "#B54708"),
    "verde": ("#DDF5E7", "#067647"),
    "cinza": ("#EEF0F3", "#5B6470"),
    "azul": ("#DBEAFE", "#1D4ED8"),
    "": ("#FFFFFF", "#344054"),
}
ROTULO = {
    "lapso": {"vencido": "Vencido · verificar", "laranja": "Até 30 dias", "amarelo": "Até 60 dias", "verde": "Até 90 dias", "cinza": "Não se aplica / interrompida", "azul": "Extinta"},
    "indulto": {"vermelho": "Crime impeditivo", "verde": "Possível", "amarelo": "A verificar", "cinza": "Não atinge", "azul": "Extinta"},
    "presc": {"vermelho": "Prescrição aparente", "": "Não prescrita", "cinza": "Sem dados", "azul": "Extinta"},
    "fd": {"vermelho": "Remição pendente", "amarelo": "Trabalho a atestar / verificar", "verde": "Em ordem", "cinza": "Sem ficha"},
    "aud": {"vermelho": "Guia demanda atenção", "amarelo": "Pontos a verificar", "verde": "Sem inconsistências", "azul": "Extinta"},
    "ext": {"vermelho": "Extinção cabível", "laranja": "Término em até 30 dias", "amarelo": "Até 60 dias / a verificar", "verde": "Término em até 90 dias", "cinza": "Sem previsão / interrompida", "azul": "Extinta (registrada)"},
}

# filtros de situação por tipo de aba: (id, rótulo, função(modelo)->bool)
def _dias(m, k):
    return m.get(k)


FILTROS = {
    "fd": [
        ("todas", "Todas"),
        ("impeditivo", "Remição pendente"),
        ("verificar", "A atestar / verificar"),
        ("ok", "Em ordem"),
        ("nao", "Sem ficha"),
    ],
    "lapso": [
        ("todas", "Todas"),
        ("vencidas", "Vencidas"),
        ("30", "Vence em até 30 dias"),
        ("60", "Vence em até 60 dias"),
        ("90", "Vence em até 90 dias"),
        ("interrompida", "Pena interrompida"),
        ("naoaplica", "Não se aplica (cumprida / livramento / aberto)"),
        ("semdata", "Sem data"),
    ],
    "indulto": [
        ("todas", "Todas"),
        ("possivel", "Possível"),
        ("verificar", "A verificar"),
        ("nao", "Não atinge / não se aplica"),
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
        ("atencao", "Guia demanda atenção"),
        ("verificar", "Pontos a verificar"),
        ("ok", "Sem inconsistências"),
    ],
    "presc": [
        ("todas", "Todas"),
        ("aparente", "Prescrição aparente"),
        ("naocorre", "Não prescrita"),
        ("semdados", "Sem dados / extinta"),
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
        if duv:
            return ("lc_duvida", "Livramento a confirmar" + (" (%s)" % rs.fmt(dl) if dl else "") + " · ver Auditoria")
        return ("lc", "Em livramento condicional" + (" desde %s" % rs.fmt(dl) if dl else ""))
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
    if est and est[0] in ("extinta", "cumprida", "lc", "lc_duvida"):
        return (est[1], None)
    pt = rs.pena_para_dias(r.get("pena_total"))
    _min = rg.carregar().get("livramento", {}).get("pena_minima_anos", 2)
    if pt and pt < _min * rs.DIAS_ANO and not r.get("livramento_previsao_seeu"):
        return ("Não cabe: pena < %s anos (art. 83 CP)" % _min, None)
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
            return ("Em %d dias" % n, cor)
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
    falta = " · falta 12m!" if "FALTA" in txt else ""
    base = txt.split(" | ")[0]
    if base.startswith("VEDAD"):
        return "Vedado (art. 1º)"
    if base.startswith("POSSÍVEL (parcial)"):
        return "Possível (parcial) · " + base.split(": ", 1)[1] + falta
    if base.startswith("POSSÍVEL"):
        return base.replace("POSSÍVEL: ", "Possível · ").split("; § 5º")[0].replace("art. 5º (todos os crimes com pena máxima ≤ 5 anos)", "art. 5º (pena máx. ≤ 5 anos)") + falta
    if base.startswith("A VERIFICAR"):
        return base.replace("A VERIFICAR: ", "A verificar · ") + falta
    if base.startswith("não se aplica: fatos"):
        return "Não se aplica (fatos posteriores)"
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
    t = rs.re.sub(r"\s*\((?:sem execução na data|fatos posteriores)\)", "", t)
    t = t.replace("Vedado (art. 1º)", "Vedado · art. 1º").replace("Excluído (art. 7º)", "Excluído · art. 7º")
    t = t.replace(" · art. 9º, ", " · ").replace("art. 5º (pena máx. ≤ 5 anos)", "art. 5º")
    t = rs.re.sub(r"^Não atinge \(.*\)$", "Não atinge", t)
    t = rs.re.sub(r"^não atinge.*$", "Não atinge", t)
    t = rs.re.sub(r"^Possível · art\. 13 \(.*\)$", "Possível · art. 13", t)
    t = t.replace("Possível (parcial) · ", "Parcial · ")
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
    if r.get("indulto_crime_impeditivo") == "SIM":
        return "vermelho"
    st = {r.get("indulto_2022_status"), r.get("indulto_2024_status"), r.get("indulto_2025_status")}
    if "possivel" in st:
        return "verde"
    if "verificar" in st or "POSSÍVEL" in (r.get("comutacao_2025", "") + r.get("comutacao_2024", "")):
        return "amarelo"
    return "cinza"


def termino(r):
    if r.get("termino_previsao_seeu"):
        return r["termino_previsao_seeu"]
    return "Interrompida" if "INTERROMPIDA" in (r.get("situacao_cumprimento") or "") else "Não consta no RSPE"


def extincao(r, presc, interr):
    """Hipóteses de extinção da pena/punibilidade aferíveis pelo RSPE."""
    hip, cor, d_ref = [], "", None
    pt = rs.pena_para_dias(r.get("pena_total")) or 0
    cump = rs.pena_para_dias(r.get("pena_cumprida"))
    term = rs.to_date(r.get("termino_previsao_seeu") or "")
    est = False
    # 1) pena cumprida
    if pt and cump is not None and cump >= pt:
        hip.append("Pena integralmente cumprida (%s de %s): extinção pelo cumprimento (CP, art. 51 e Tema 931/STJ: multa pendente não obsta)" % (rs.dias_para_pena(cump), rs.dias_para_pena(pt)))
        cor, d_ref = "vermelho", HOJE
    elif term and term <= HOJE:
        hip.append("Término da pena previsto para %s%s já alcançado" % (rs.fmt(term), " (est.)" if est else ""))
        cor, d_ref = "vermelho", term
    # 2) livramento condicional: período de prova expirado sem revogação
    inc = r.get("_incidentes", [])
    _lc_ok, _ = rs.livramento_em_curso(r, inc)
    lcs = [i for i in inc if i.get("situacao") == "CONCEDIDO" and rs.e_incidente_livramento(i)] if _lc_ok else []
    if lcs:
        dlc = max((rs.to_date(i.get("data_referencia") or i.get("data_decisao") or i.get("complemento") or "") or date.min for i in lcs))
        revog = any("REVOG" in ((j.get("tipo") or "") + " " + (j.get("complemento") or "")).upper()
                    and (rs.to_date(j.get("data_referencia") or j.get("data_decisao") or "") or date.min) > dlc for j in inc)
        duv = rs.duvidas_livramento(r, r.get("_eventos", []), inc, dlc if dlc != date.min else None) if not revog else []
        if dlc != date.min and not revog and duv:
            hip.append("Livramento condicional desde %s com situação incerta no RSPE (%s): conferir revogação/suspensão e o fim do período de prova (CP, arts. 86 a 90) - ver Auditoria" % (rs.fmt(dlc), "; ".join(duv)))
            cor = "amarelo_lc"
        elif dlc != date.min and not revog and term:
            if term <= HOJE:
                hip.append("Livramento condicional desde %s com período de prova expirado em %s sem revogação (CP, arts. 82 e 90)" % (rs.fmt(dlc), rs.fmt(term)))
                cor = "vermelho"
    # 3) prescrição / detração
    for l in presc.get("presc_linhas", []):
        if (l.get("ppe_status") or "").startswith("Pena cumprida por detração"):
            hip.append("%s: %s - CP, art. 42; LEP, art. 66, II" % (l["crime"], l["ppe_status"]))
            cor = "vermelho"
            continue
        if l.get("ppe_cor") == "vermelho":
            hip.append("Prescrição da pretensão executória aparente: %s (%s) - CP, art. 107, IV" % (l["crime"], l.get("ppe_previsao")))
            cor = "vermelho"
        if l.get("retro_cor") == "vermelho":
            hip.append("Prescrição da pretensão punitiva aparente: %s - CP, art. 107, IV" % l["crime"])
            cor = "vermelho"
    # 4) indulto
    parcial = False
    for ano in ("2022", "2024", "2025"):
        if r.get("indulto_%s_status" % ano) == "possivel":
            txt = (r.get("indulto_%s" % ano) or "").split(" | ")[0]
            if txt.startswith("POSSÍVEL (parcial)"):
                # indulto de parte dos crimes: extingue só esses crimes, não a execução
                hip.append("Indulto %s parcial (%s) - extingue só esses crimes; a execução prossegue pelos demais (CP, art. 107, II)" % (ano, txt.split(": ", 1)[-1]))
                parcial = True
            else:
                hip.append("Indulto %s possível (%s) - CP, art. 107, II" % (ano, txt.replace("POSSÍVEL: ", "")))
                cor = "vermelho"
    # multa cominada: não obsta a extinção (hipossuficiência presumida - Defensoria)
    com_multa = any(re.search(r"\b(E|e)\s+Multa", c.get("tipo_penal") or "") for c in r.get("_crimes", []) if not c.get("extinto", "").upper().startswith("S"))
    multa_txt = ("Multa cominada: não obsta a extinção - hipossuficiência presumida (STJ Tema 931; STF ADI 7.032)" if com_multa else "")
    # crimes já extintos no RSPE
    ext = ["%s%s%s" % (rs.crimes_curto([c]).replace(" (extinto)", ""), (" · " + c["extincao_motivo"].lower()) if c.get("extincao_motivo") else "",
                       (" em " + c["data_extincao"]) if c.get("data_extincao") else "")
           for c in r.get("_crimes", []) if c.get("extinto", "").upper().startswith("S")]
    todos_extintos = bool(r.get("_crimes")) and all(c.get("extinto", "").upper().startswith("S") for c in r.get("_crimes", []))
    if r.get("execucao_extinta") or todos_extintos:
        hip.insert(0, "Execução já extinta segundo o RSPE (%s)" % (r.get("execucao_extinta") or "todos os crimes extintos"))
        cor = "extinta"
    # prazo do término
    duvida_lc = cor == "amarelo_lc"
    ja_extinta = cor == "extinta"
    parcial_ext = parcial and cor not in ("vermelho", "extinta", "amarelo_lc")
    if duvida_lc:
        cor = "amarelo"
    elif ja_extinta:
        cor = "azul"
    elif parcial_ext:
        cor = "amarelo"
    elif cor != "vermelho":
        if interr and not term:
            cor = "cinza"
        elif term:
            n = (term - HOJE).days
            cor = next((c for lim, c in ALERTAS_DIAS if n <= lim), "")
        else:
            cor = "cinza"
    return {
        "ext_hipoteses": "; ".join(hip) if hip else ("Nenhuma hipótese objetiva no RSPE" if not interr else "Pena interrompida - sem previsão"),
        "ext_cor": cor,
        "ext_termino": (rs.fmt(term) + (" (est.)" if est else "")) if term else ("Interrompida" if interr else ""),
        "ext_dias": (term - HOJE).days if term else None,
        "ext_sit": ("Pena extinta (registrada)" if ja_extinta else "A verificar (livramento)" if duvida_lc else "Extinção parcial cabível" if parcial_ext else (("Extinção cabível" if cor == "vermelho" else situacao(term)[0].replace("Vence", "Término").replace("Em ", "Término em ")) if (term or cor == "vermelho") else "")),
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
    if r.get("falta_12m") == "SIM":
        partes.append("Falta nos últimos 12 meses: " + (r.get("falta_12m_detalhe") or "sim"))
    return " · ".join(partes)


def _dias_para(d):
    if d == "atingido":
        return 0
    if isinstance(d, date):
        return (d - HOJE).days
    return None


def modelo(r, baixas=None, ficha=None):
    """Registro extraído -> dict plano com tudo que as abas mostram. baixas: {chave: {obs, data}} da auditoria.
    ficha: Ficha Disciplinar do SIAPEN já lida (rspe_ficha.extrair), se houver."""
    baixas = baixas or {}
    interr = "INTERROMPIDA" in (r.get("situacao_cumprimento") or "")
    ptxt, pd = data_progressao(r)
    ltxt, ld = data_livramento(r)
    est = estado_execucao(r)
    psit, pcor = situacao(pd, interr)
    lsit, lcor = situacao(ld, interr)
    if est:
        psit, pcor = ({"extinta": "Pena extinta", "cumprida": "Pena cumprida", "lc": "Em livramento", "aberto": "Já no aberto", "lc_duvida": "A verificar (livramento)"}[est[0]],
                      "amarelo" if est[0] == "lc_duvida" else "azul" if est[0] == "extinta" else "cinza")
        if est[0] in ("extinta", "cumprida", "lc", "lc_duvida"):
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
            aud["aud_itens"].insert(0, {"nivel": "verificar", "titulo": "Ficha disciplinar: falha ao confrontar (%s)" % e, "detalhe": "", "fundamento": ""})
    aud["aud_itens"].sort(key=lambda i: {"alerta": 0, "verificar": 1, "info": 2, "ok": 3}.get(i["nivel"], 9))
    for it in aud["aud_itens"]:
        it["chave"] = hashlib.sha1(it["titulo"].encode("utf-8")).hexdigest()[:12]
        b = baixas.get(it["chave"])
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
    aud["aud_resumo"] = ("Guia demanda atenção: %d alerta(s), %d a verificar" % (n_al, n_ve)) if n_al else (("%d ponto(s) a verificar" % n_ve) if n_ve else "Sem inconsistências pendentes")
    if n_bx:
        aud["aud_resumo"] += " · %d baixado(s)" % n_bx
    aud["aud_info"] = n_info
    falta = ("Sim · " + (r.get("falta_12m_detalhe") or "")) if r.get("falta_12m") == "SIM" else "Não consta"
    return {
        "id": r.get("processo_execucao") or r.get("arquivo"),
        "nome": r.get("nome", ""),
        "proc": r.get("processo_execucao", ""),
        "geral_cor": "azul" if execucao_extinta(r) else "",
        "regime": ("Livramento condicional" if (est and est[0] == "lc") else
                   ("Livramento? (RSPE: %s)" % (r.get("regime_atual") or "").replace(" - ATIVO", "") if (est and est[0] == "lc_duvida") else
                    (r.get("regime_atual") or "").replace(" - ATIVO", ""))),
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
        **rf.comparativo(r, ficha, HOJE),
        "ficha_resumo": rf.resumo(ficha) if ficha else "",
        "ficha_tem": bool(ficha),
        "ficha": ({k: ficha.get(k) for k in ("nome", "rgi", "cpf", "unidade", "data_entrada", "data_prisao", "conduta", "data_impressao", "trabalho", "atestados",
                                             "dias_trabalhados_atestados", "dias_remidos_atestados", "faltas", "regressoes", "restabelecimentos", "recusa_trabalho", "isolamentos", "estudo", "autos", "importado_em")}
                  if ficha else None),
        "aud_info": aud.get("aud_info", 0),
        "aud_cor": "azul" if execucao_extinta(r) else {"atencao": "vermelho", "verificar": "amarelo", "ok": "verde"}[aud["aud_status"]],
        "aud_status": aud["aud_status"], "aud_resumo": aud["aud_resumo"], "aud_alertas": aud["aud_alertas"],
        "aud_verificar": aud["aud_verificar"], "aud_itens": aud["aud_itens"], "aud_n": len(aud["aud_itens"]),
        "aud_base": aud["aud_base"],
        "frac_prog": r.get("fracao_progressao_aplicada", ""),
        "dbase": r.get("data_base_seeu") or r.get("data_base", ""),
        "ped_prog": pedidos(r, "PROGRESS"),
        "liv": ltxt, "liv_sit": lsit, "liv_cor": lcor,
        "frac_liv": r.get("fracao_livramento_aplicada", ""),
        "ped_liv": pedidos(r, "LIVRAMENTO"),
        "falta": falta,
        "falta_sim": r.get("falta_12m") == "SIM",
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
             "frac_prog": c.get("fracao_progressao"), "frac_liv": c.get("fracao_livramento")}
            for c in r.get("_crimes", [])],
        "incidentes": [
            {"sit": i.get("situacao"), "tipo": i.get("tipo"), "comp": i.get("complemento"),
             "dec": i.get("data_decisao"), "ref": i.get("data_referencia")}
            for i in r.get("_incidentes", [])],
    }


# abas: colunas (chave, título, peso), campo de cor, campo "status" (pílula), tipo de legenda
PRESC_SUB = [("crime", "Crime", 14), ("pena", "Pena", 8), ("fato", "Fato", 9), ("denuncia", "Denúncia", 9), ("sentenca", "Sentença", 9),
             ("transito", "Trânsito", 9), ("prazo_ppp", "Prazo PPP", 9), ("retro_status", "Retroativa / intercorrente", 20),
             ("prazo_ppe", "Prazo PPE", 11), ("ppe_termo", "Termo inicial", 9), ("ppe_status", "Executória", 22)]
ABAS = [
    {"id": "geral", "titulo": "Geral", "cor": "geral_cor", "legenda": "lapso", "sem_stats": True,
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 17), ("regime", "Regime", 9),
              ("prog", "Progressão", 15), ("liv", "Livramento", 15), ("termino", "Término", 10), ("crimes", "Crimes", 22)],
     "pilulas": {}},
    {"id": "prog", "titulo": "Progressão", "cor": "prog_cor", "legenda": "lapso",
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 18), ("regime", "Regime", 9),
              ("prog", "Data da progressão", 16), ("prog_sit", "Situação", 14), ("falta", "Falta (12 meses)", 16)],
     "pilulas": {"prog_sit": "prog_cor"}},
    {"id": "liv", "titulo": "Livramento", "cor": "liv_cor", "legenda": "lapso",
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 18), ("regime", "Regime", 9),
              ("liv", "Data do livramento", 16), ("liv_sit", "Situação", 14), ("falta", "Falta (12 meses)", 16)],
     "pilulas": {"liv_sit": "liv_cor"}},
    {"id": "ind", "titulo": "Indulto / Comutação", "cor": "ind_cor", "legenda": "indulto",
     "cols": [("nome", "Nome", 16), ("proc", "Nº da execução", 14), ("regime", "Regime", 8),
              ("imp", "Impeditivo (art. 1º)", 12),
              ("i22", "Indulto 2022", 10), ("i24", "Indulto 2024", 10), ("c24", "Comutação 2024", 10), ("i25", "Indulto 2025", 10), ("c25", "Comutação 2025", 10)],
     "pilulas": {"imp": "ind_cor", "i22": "i22_cor", "i24": "i24_cor", "c24": "c24_cor", "i25": "i25_cor", "c25": "c25_cor"}},
    {"id": "presc", "titulo": "Prescrição", "cor": "presc_cor", "legenda": "presc", "expansivel": True,
     "cols": [("nome", "Nome", 20), ("proc", "Nº da execução", 17), ("regime", "Regime", 8),
              ("presc_retro", "Pretensão punitiva", 18), ("presc_ppe", "Pretensão executória", 26), ("presc_prox", "Prescrita em", 9)],
     "pilulas": {},
     "sub": "presc_linhas", "sub_cols": PRESC_SUB, "sub_pilulas": {"retro_status": "retro_cor", "ppe_status": "ppe_cor"}, "sub_calc": True},
    {"id": "ext", "titulo": "Extinção", "cor": "ext_cor", "legenda": "ext",
     "cols": [("nome", "Nome", 20), ("proc", "Nº da execução", 17), ("regime", "Regime", 8),
              ("ext_termino", "Término", 10), ("ext_sit", "Situação", 12), ("ext_hipoteses", "Hipóteses de extinção no RSPE", 46)],
     "pilulas": {"ext_sit": "ext_cor"}},
    {"id": "fd", "titulo": "Ficha disciplinar", "cor": "fd_cor", "legenda": "fd", "expansivel": True,
     "cols": [("nome", "Nome", 20), ("proc", "Nº da execução", 15), ("fd_trab", "Trabalho atual", 18),
              ("fd_remidos", "Remidos ficha / RSPE", 12), ("fd_atestar", "A atestar", 14), ("fd_sit", "Situação", 14)],
     "pilulas": {"fd_sit": "fd_cor"},
     "sub": "fd_linhas", "sub_cols": [("emp", "Emprego", 14), ("per", "Período", 14), ("dias", "Dias", 6), ("at", "Atestado", 22), ("rspe", "Remição no RSPE", 18), ("sit", "Situação / providência", 26)],
     "sub_pilulas": {"sit": "cor"}},
    {"id": "aud", "titulo": "Auditoria", "cor": "aud_cor", "legenda": "aud", "expansivel": True,
     "cols": [("nome", "Nome", 22), ("proc", "Nº da execução", 17),
              ("aud_resumo", "Resultado da auditoria", 28), ("aud_alertas", "Alertas", 6), ("aud_verificar", "A verificar", 7)],
     "pilulas": {"aud_resumo": "aud_cor"},
     "sub": "aud_itens", "sub_cols": [("nivel_txt", "Nível", 9), ("titulo", "Ponto auditado", 26), ("detalhe", "O que foi encontrado", 40), ("fundamento", "Fundamento", 24)],
     "sub_pilulas": {"nivel_txt": "nivel_cor"}, "sub_calc": False, "sub_baixa": True},
]
ABA_POR_ID = {a["id"]: a for a in ABAS}
for _a in ABAS:
    _a["filtros"] = FILTROS.get(_a["id"], FILTROS["indulto"] if _a["id"] == "ind" else FILTROS["lapso"])
    _a["campo_dias"] = {"prog": "prog_dias", "liv": "liv_dias", "presc": "presc_dias", "ext": "ext_dias"}.get(_a["id"], "")
