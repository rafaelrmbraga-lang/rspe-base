"""Construtores dos casos simulados (RSPE no formato de assistidos.dados; ficha no formato de fichas.dados) e das
verificações. Contas próprias, independentes do código do APTO: ano de 365 dias, mês de 30, dia do começo conta
(CP, art. 10), fração em dias arredondada para baixo."""
from datetime import date, timedelta

GER = date(2026, 10, 5)     # data de geração dos RSPE simulados
HOJE = date(2026, 10, 12)   # data de referência fixada no executor

CP = "2848/40 - Código Penal"
DROGAS = "11343/06 - Lei de Drogas"


def D(s):
    d, m, a = s.split("/")
    return date(int(a), int(m), int(d))


def F(d):
    return d.strftime("%d/%m/%Y")


def amd(n):
    """dias -> (anos, meses, dias) na convenção do SEEU (365/30)."""
    a, r = divmod(int(n), 365)
    m, d = divmod(r, 30)
    return a, m, d


def pena_imp(n):
    a, m, d = amd(n)
    return "%d ano(s), %d mês(es) e %d dia(s)" % (a, m, d)


def pena_cab(n):
    a, m, d = amd(n)
    return "%da%dm%dd" % (a, m, d)


def anos(a, m=0, d=0):
    return a * 365 + m * 30 + d


def mais_anos(d0, a, meses=0):
    """d0 + a anos + meses pelo calendário (prazo prescricional): termina na véspera do mesmo dia (CP, art. 10)."""
    y, mo = d0.year + a, d0.month + meses
    y += (mo - 1) // 12
    mo = (mo - 1) % 12 + 1
    try:
        alvo = d0.replace(year=y, month=mo)
    except ValueError:
        alvo = date(y, mo, 28) + timedelta(days=1)
        alvo = alvo.replace(day=1) if alvo.month != mo else alvo
    return alvo - timedelta(days=1)


_n = [0]


def proc_crim(k, ano=2020):
    return "%07d-00.%d.8.12.0001" % (8800000 + k, ano)


def crime(proc, artigo, pena_dias, fato, sentenca=None, transito=None, lei=CP, tipo="CAPUT: tipo simulado, Reclusão: 1 a 4 anos E Multa",
          fp="1/6 - Comum", fl="1/3 - Comum Primário", vga="N", morte="N", rc="N", re_="N", orcrim="N", denuncia=None,
          transito_mp=None, extinto="Não", pena_total_processo=None, regime="Fechado", **kw):
    fd = D(fato)
    sentenca = sentenca or F(fd + timedelta(days=200))
    transito = transito if transito is not None else F(D(sentenca) + timedelta(days=60))
    c = {"processo_criminal": proc, "processo_situacao": "", "tipo_processo": "ACAO PENAL", "vara_condenacao": "Campo Grande, 1ª Vara",
         "data_denuncia": denuncia or F(fd + timedelta(days=30)), "data_sentenca": sentenca,
         "transito_mp": transito_mp if transito_mp is not None else transito, "transito_processo": transito,
         "pena_total_processo": pena_total_processo or ("%s - PENA ORIGINÁRIA" % pena_cab(pena_dias)), "regime_sentenca": regime,
         "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena_imp(pena_dias) if pena_dias else "",
         "data_infracao": fato, "vga": vga, "resultado_morte": morte, "reincidente_comum": rc, "reincidente_especifico": re_,
         "comando_orcrim": orcrim, "fracao_progressao": fp, "fracao_livramento": fl, "extinto": extinto, "suspenso": "Não"}
    c.update(kw)
    c["_dias"] = pena_dias or 0
    return c


def ev(tipo, motivo, data, procs=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": procs}


def prisao(data, procs, motivo="PRISÃO EM FLAGRANTE"):
    return ev("PRISÃO/INÍCIO DE CUMPRIMENTO", motivo, data, procs)


def interr(data, motivo="FUGA", procs=""):
    return ev("INTERRUPÇÃO", motivo, data, procs)


def inc(tipo, compl, dec, ref, sit="CONCEDIDO", procs="", motivo=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": procs, "situacao": sit}


REG = "FIXAÇÃO/ALTERAÇÃO DE REGIME"


def rspe(k, crimes, eventos=(), incidentes=(), ini=None, pena=None, interrompidos=0, remidos=0, prog=None, liv=None, term=None,
         db=None, regime="Fechado - ATIVO", fp="", fl="", nasc="01/01/1975", cpf=None, status="ATIVO", ger=GER, **kw):
    """Cabeçalho coerente: pena cumprida = dias de custódia desde ini (inclusive) - interrupções + remição; término = véspera de
    ini + pena (dia do começo conta) ajustado; previsões informadas pelo caso."""
    pid = "%07d-00.2026.8.12.0001" % (9900000 + k)
    pena = pena if pena is not None else sum((x.get("_dias") or 0) for x in crimes)
    if ini:
        cumprida = (ger - D(ini)).days + 1 - interrompidos + remidos
        cumprida = max(0, min(cumprida, pena))
    else:
        cumprida = 0
    # remanescente como o SEEU imprime: pena total - cumprida em anos/meses/dias (12 meses = 1 ano, 30 dias = 1 mês)
    ta, tm, td = amd(pena)
    ca, cm, cd = amd(cumprida)
    ra_, rm_, rd_ = ta - ca, tm - cm, td - cd
    if rd_ < 0:
        rd_ += 30; rm_ -= 1
    if rm_ < 0:
        rm_ += 12; ra_ -= 1
    rem = max(0, ra_ * 365 + rm_ * 30 + rd_)
    # término coerente com a contagem em dias (dia do começo conta): início + pena + interrupções - remição - 1
    termo = term if term is not None else (F(D(ini) + timedelta(days=pena - 1 + interrompidos - remidos)) if ini else "")
    for x in crimes:
        x.pop("_dias", None)
    r = {"arquivo": "SIMULADO_%03d.pdf" % k, "nome": "SIMULADO CASO %03d" % k, "processo_execucao": pid, "cpf": cpf or "%011d" % (90000000000 + k),
         "nome_mae": "MAE SIMULADA %03d" % k, "rg": "", "data_nascimento": nasc, "numero_antigo": "", "tribunal": "TJMS",
         "vara": "TJMS - 1ª VARA DE EXECUÇÃO PENAL", "comarca": "CAMPO GRANDE", "status_execucao": status,
         "regime_atual": regime, "pena_total": pena_cab(pena), "pena_cumprida": pena_cab(cumprida), "pena_remanescente": "%da%dm%dd" % (ra_, rm_, rd_) if rem else "0a0m0d",
         "total_interrupcoes": pena_cab(interrompidos), "saldo_remidos": "%d dias (%d dias remidos - 0 dias perdidos)" % (remidos, remidos),
         "data_base_seeu": db or ini or "", "livramento_data_base_seeu": ini or "", "progressao_previsao_seeu": prog or "",
         "livramento_previsao_seeu": liv or "", "termino_previsao_seeu": termo, "fracao_progressao_aplicada": fp,
         "fracao_livramento_aplicada": fl, "progressao_obs_seeu": "", "livramento_obs_seeu": "", "data_geracao_rspe": F(ger),
         "versao_leitura_rspe": 4, "_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes),
         "_hash": "sim%03d" % k}
    r.update(kw)
    return r


def C(campo, op, v=None, nota=""):
    return {"t": "campo", "campo": campo, "op": op, "v": v, "nota": nota}


def AUD(tipo, presente=True, contem=None, nivel=None, nota=""):
    return {"t": "aud", "tipo": tipo, "presente": presente, "contem": contem, "nivel": nivel, "nota": nota}


def P(i, campo, op, v=None, nota=""):
    return {"t": "presc", "i": i, "campo": campo, "op": op, "v": v, "nota": nota}


def caso(k, grupo, titulo, conta, r, checks, ficha=None, manuais=None, extra=None, acoes=None):
    return {"acoes": acoes or [], "id": "S%03d" % k, "grupo": grupo, "titulo": titulo, "conta": conta, "processo": r["processo_execucao"], "rspe": r,
            "ficha": ficha, "manuais": manuais or {}, "extra_rspe": extra or [], "checks": checks}
