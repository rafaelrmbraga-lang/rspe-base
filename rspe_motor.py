# -*- coding: utf-8 -*-
"""Motor do APTO: monta a análise de um assistido (todas as abas) a partir do registro do RSPE e da fatia do contexto da base.
É o MESMO código para o APTO (rspe_app importa daqui) e para a extensão do navegador (o painel no SEEU roda este módulo no
Pyodide): mesma entrada (registro + fatia do contexto + data de referência) = mesmo resultado. Sem interface, sem base, sem
arquivos: só as regras (rspe_view, rspe_ficha, rspe_decretos, rspe_regras, rspe_scraper)."""
import hashlib
import json
import logging
import re
from datetime import date, datetime

import rspe_scraper as rs
import rspe_view as rv
import rspe_ficha as rf
import rspe_regras as rg
import rspe_decretos as rd

# versão do programa que entra na impressão digital do cálculo (_chave_calculo): o APTO preenche com a sua VERSAO ao importar;
# a extensão, com a versão gravada no pacote do motor (motor.json), a mesma do APTO que o gerou
VERSAO = ""

_mesma_mae = rf.mesma_mae


def _so_digitos(x):
    return re.sub(r"\D", "", x or "")


def _ficha_prova(f, r):
    """A ficha é desta pessoa por dado objetivo: mesmo CPF, autos da ficha com o número desta execução (ou de uma ação penal
    dela) ou mesma data de nascimento com nome parecido."""
    cpf_f, cpf_r = _so_digitos(f.get("cpf")), _so_digitos(r.get("cpf"))
    if len(cpf_f) == 11 and cpf_f == cpf_r:
        return True
    autos = {_so_digitos(a) for a in f.get("autos") or []} - {""}
    procs = {_so_digitos(r.get("processo_execucao"))} | {_so_digitos(c.get("processo_criminal")) for c in r.get("_crimes") or []}
    if autos & (procs - {""}):
        return True
    import difflib
    return bool(f.get("data_nascimento") and f.get("data_nascimento") == r.get("data_nascimento")
                and difflib.SequenceMatcher(None, _norm(f.get("nome")), _norm(r.get("nome"))).ratio() >= 0.9)


def _ficha_alternativa(fichas, r):
    """Ficha guardada pelo nome que não casou pela grafia exata (Fretez/Fretes, Cezar/Cesar, Sousa/Souza) ou que ficou de fora por
    homônimo: vale só com prova objetiva (CPF, autos ou nascimento - _ficha_prova) e nome parecido; havendo mais de uma, a mais
    recente."""
    import difflib
    nn = _norm(r.get("nome"))
    if not nn:
        return None
    cand = []
    for k, f in fichas.items():
        if not k.startswith("nome:") or not isinstance(f, dict):
            continue
        nf = _norm(f.get("nome") or k[5:])
        if nf[:1] != nn[:1]:
            continue
        mesmo_cpf = len(_so_digitos(f.get("cpf"))) == 11 and _so_digitos(f.get("cpf")) == _so_digitos(r.get("cpf"))
        if (mesmo_cpf or difflib.SequenceMatcher(None, nf, nn).ratio() >= 0.85) and _ficha_prova(f, r):
            cand.append(f)
    return max(cand, key=lambda f: rs.to_date(f.get("data_impressao") or "") or date.min) if cand else None


def _fichas_candidatas(fichas, r):
    """Fichas guardadas pelo nome, de nome igual ou parecido, que não vincularam por falta de prova (CPF, autos ou nascimento):
    vão para a Auditoria, com os dados lado a lado, para o operador vincular se for a mesma pessoa."""
    import difflib
    nn = _norm(r.get("nome"))
    out = []
    for k, f in fichas.items():
        if not k.startswith("nome:") or k.startswith("nome:~") or not isinstance(f, dict):
            continue
        nf = _norm(f.get("nome") or k[5:])
        cf, cr = _so_digitos(f.get("cpf")), _so_digitos(r.get("cpf"))
        if (len(cf) == 11 and len(cr) == 11 and cf != cr) or (f.get("data_nascimento") and r.get("data_nascimento")
                                                              and f["data_nascimento"] != r["data_nascimento"]):
            continue  # CPF ou nascimento diferentes: é de outra pessoa, não há dúvida a resolver
        if nf[:1] == nn[:1] and difflib.SequenceMatcher(None, nf, nn).ratio() >= 0.85:
            out.append({"chave": k, "nome": f.get("nome") or "", "cpf": f.get("cpf") or "", "nasc": f.get("data_nascimento") or "",
                        "mae": f.get("nome_mae") or "", "impressa": f.get("data_impressao") or ""})
    return out[:3]


def _norm(txt):
    import unicodedata
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    return " ".join(t.upper().split())


def _montar_modelo(r, ctx):
    """Modelo de um assistido (todas as abas) a partir do registro gravado e das tabelas auxiliares. Função do módulo (sem
    a base aberta), para montar a base grande em processos paralelos; devolve (modelo, baixas a migrar)."""
    migrar = []
    baixas, fichas, manuais, ajustes = ctx["baixas"], ctx["fichas"], ctx["manuais"], ctx["ajustes"]
    dmanuais, peds, _homonimos = ctx["dmanuais"], ctx["peds"], ctx["homonimos"]
    # dados que o RSPE não trouxe: informados na Auditoria ou, para a data de nascimento, lidos da ficha disciplinar
    _ch0 = r.get("processo_execucao") or r.get("arquivo")
    _dm = dmanuais.get(_ch0, {})
    r["_outras_condenacoes"] = (ctx.get("outras_cond") or {}).get(_ch0, [])
    r["_outras_execucoes"] = (ctx.get("outras_exec") or {}).get(_ch0, [])
    r["_homonimos_base"] = (ctx.get("homon_det") or {}).get(_ch0, [])
    _n0 = _norm(r.get("nome", ""))
    _f0 = fichas.get(_ch0) or (fichas.get("nome:" + _n0) if _homonimos.get(_n0, 0) == 1 else None)
    if _f0 and _f0 is not fichas.get(_ch0) and not _mesma_mae(_norm(_f0.get("nome_mae") or ""), _norm(r.get("nome_mae") or "")) \
            and not _ficha_prova(_f0, r):
        _f0 = None  # ficha de homônimo: a mãe não confere (nem CPF, autos ou nascimento)
    if not _f0:
        # ficha vinculada a outra execução da mesma pessoa (mesmo CPF): a ficha é da pessoa, vale para a execução em curso
        _fo = [fichas[o] for o in (ctx.get("outros_procs") or {}).get(_ch0, []) if fichas.get(o)]
        _f0 = max(_fo, key=lambda f: rs.to_date(f.get("data_impressao") or "") or date.min) if _fo else None
    if not _f0:
        # ficha guardada pelo nome com grafia diferente ou bloqueada por homônimo: só com CPF, autos ou nascimento conferindo
        _f0 = fichas.get("nome:~alt") or _ficha_alternativa(fichas, r)
    # fichas desvinculadas pelo operador (Auditoria): não voltam a este assistido, nem como candidatas
    _rec = set(((_dm.get("ficha_recusada") or {}).get("valor") or "").split("\n")) - {""}
    if _f0 and rf.assinatura_ficha(_f0) in _rec:
        _f0 = None
    r["_ficha_recusada"] = "/".join((_dm["ficha_recusada"]["data"] or "")[:10].split("-")[::-1]) if _rec else ""
    r["_fichas_cand"] = [] if _f0 else [c for c in (fichas["~cands"] if "~cands" in fichas else _fichas_candidatas(fichas, r))
                                        if rf.assinatura_ficha({"nome": c["nome"], "cpf": c["cpf"], "data_nascimento": c["nasc"]}) not in _rec]
    r.pop("_nasc_fonte", None); r.pop("_nasc_data", None)
    if _dm.get("data_nascimento"):
        if r.get("data_nascimento") != _dm["data_nascimento"]["valor"]:
            r["_nasc_rspe"] = r.get("data_nascimento") or ""
        r["data_nascimento"] = _dm["data_nascimento"]["valor"]
        r["_nasc_data"] = "/".join(_dm["data_nascimento"]["data"][:10].split("-")[::-1])
        r["_nasc_fonte"] = "informada pelo operador"
    elif not r.get("data_nascimento") and _f0 and (_f0.get("data_nascimento") or ""):
        r["data_nascimento"] = _f0["data_nascimento"]
        r["_nasc_fonte"] = "lida da ficha disciplinar do SIAPEN"
        r["_nasc_data"] = ""
    # nascimento do RSPE diferente do da ficha (operador ainda não informou a correta): nenhuma fonte prevalece sozinha - o
    # requisito de idade que muda com a data da ficha fica a verificar (decretos e art. 115 do CP)
    r.pop("_nasc_alt", None)
    if _f0 and not _dm.get("data_nascimento"):
        _na, _nb = rs.to_date(r.get("data_nascimento") or ""), rs.to_date((_f0.get("data_nascimento") or "").strip())
        if _na and _nb and _na != _nb and rf.nascimento_muda_marco(r, _na, _nb):
            r["_nasc_alt"] = rs.fmt(_nb)
    # RSPE x ficha: retomada do cumprimento omitida no RSPE é lançada pela ficha; divergência vira alerta
    try:
        rf.reconciliar_eventos(r, _f0)
    except Exception:
        logging.getLogger("rspe").exception("reconciliação com a ficha %s", _ch0)
    # faltas graves da ficha disciplinar que o RSPE não traz: entram como falta a apurar
    try:
        rs.faltas_da_ficha(r, _f0, rv.HOJE)
        rs.explicar_indicios_ficha(r, _f0, rv.HOJE)  # regressão/perda/pendente: a ficha explica?
    except Exception:
        logging.getLogger("rspe").exception("faltas da ficha %s", _ch0)
    # sexo para a concordância dos textos (SAP, fundamentações): o informado pelo operador; senão o cadastro da ficha
    # (sexo biológico ou unidade feminina). Sem isso, o texto fica neutro; o nome não serve de indício
    _sx = ((_dm.get("sexo") or {}).get("valor") or "")
    if not _sx and _f0:
        _sx = _f0.get("sexo") or ("F" if "FEMININ" in rs._sem_acento(_f0.get("unidade") or "").upper() else "")
    r["_sexo"] = _sx
    r["_sexo_fonte"] = "operador" if (_dm.get("sexo") or {}).get("valor") else ("ficha" if _sx else "")
    # data-base corrigida pelo operador ("dd/mm/aaaa|motivo"): refaz a previsão de progressão em todas as abas
    r.pop("_db_manual", None)
    if (_dm.get("data_base") or {}).get("valor"):
        r["_db_manual"] = _dm["data_base"]["valor"]
    # decisões do operador sobre indícios de falta (fuga, pendente, perda sem falta): valem em todas as abas
    rs.aplicar_decisoes_falta(r, {k.split("|", 1)[1]: v["valor"] for k, v in _dm.items() if k.startswith("falta|")})
    for _c in r.get("_crimes", []):
        _c.pop("_pena_max_inf", None)
        _v = _dm.get("pena_max|" + rs.chave_pena_max(_c))
        if _v:
            _c["_pena_max_inf"] = rs.pena_livre(_v["valor"])
            _c["_pena_max_data"] = "/".join(_v["data"][:10].split("-")[::-1])
    # dados do cabeçalho que o RSPE não trouxe, informados pelo operador na Auditoria ("Faltam dados"): entram antes da análise
    r.pop("_manuais", None)
    for _k, _v in _dm.items():
        if _k.startswith("rspe|") and _k[5:] in rs.CAMPOS_MANUAIS and _v.get("valor") and not r.get(_k[5:]):
            r[_k[5:]] = rs.valor_manual(_k[5:], _v["valor"])
            if _k[5:] == "regime_atual":
                r[_k[5:]] = r[_k[5:]].capitalize()  # "Semiaberto", como o RSPE imprime (não "SEMIABERTO")
            r.setdefault("_manuais", {})[_k[5:]] = {"valor": r[_k[5:]], "data": "/".join(_v["data"][:10].split("-")[::-1])}
    try:
        imp = r.get("importado_em")
        r = rs.reprocessar(r)  # análise refeita com as regras desta versão (a leitura do PDF fica como foi gravada)
        r["importado_em"] = imp
    except Exception:
        pass
    ch = r.get("processo_execucao") or r.get("arquivo")
    r["_presc_ajustes"] = ajustes.get(ch, {})  # dados de prescrição preenchidos/corrigidos pelo operador (só em memória)
    _nn = _norm(r.get("nome", ""))
    ficha = _f0 if ch == _ch0 else (fichas.get(ch) or (fichas.get("nome:" + _nn) if _homonimos.get(_nn, 0) == 1 else None))
    # um registro com dado ilegível não pode derrubar a base: tenta sem a ficha e, se ainda falhar, mostra o
    # registro com o aviso da falha
    try:
        m = rv.modelo(r, baixas.get(ch, {}), ficha, manuais.get(ch, []))
    except Exception as e:
        logging.getLogger("rspe").exception("falha ao montar %s", ch)
        try:
            # o aviso entra antes da contagem: conta no resumo e na cor, e a baixa dele fica gravada
            m = rv.modelo(r, baixas.get(ch, {}), None, manuais.get(ch, []),
                          extras=[rv.item_falha("Ficha disciplinar ignorada: falha ao ler (%s)" % e, "falha-ficha")])
        except Exception as e2:
            m = rv.modelo_erro(r, e2, baixas.get(ch, {}))
    m["sexo"], m["sexo_fonte"] = r.get("_sexo") or "", r.get("_sexo_fonte") or ""
    m["ficha_chave"] = (ficha or {}).get("_chave") or ""  # de onde veio a ficha exibida (processo, outra execução ou nome)
    # baixas gravadas pelo título (até a 6.15.11): passam para a chave estável (tipo do ponto + crime)
    for it in m.get("aud_itens") or []:
        if it.get("migrar_de"):
            migrar.append((ch, it["migrar_de"], it["chave"]))
    m["pedidos"] = peds.get(ch, {})  # pedidos já feitos, por aba (coluna "Pedido")
    m["hist_n"] = ctx["hist_n"].get(ch, 1)
    m["fixado"] = ch in ctx["fixados"]
    try:
        m["dec"] = rv.json_seguro(rd.avaliar(m.get("_final") or r, rv.HOJE))  # aba Indulto: todos os decretos desde o início do cumprimento
    except Exception:
        logging.getLogger("rspe").exception("decretos %s", ch)
        m["dec"] = {"inicio": "", "decretos": []}  # RSPEs guardados no histórico (botão "Histórico · N" da aba Geral)
    try:
        # remição pendente que, declarada, já dá um benefício: ícone de prioridade ao lado do nome
        m["rem_prio"] = rv.prioridade_remicao(m, m.get("_final") or r)
    except Exception:
        logging.getLogger("rspe").exception("prioridade da remição %s", ch)
        m["rem_prio"] = []
    # pedido do indulto (por decreto): a situação atual do decreto, para a tela comparar com a da marcação (ref)
    if any(k.startswith("ind_") for k in m["pedidos"]):
        m["pedidos"] = {k: (dict(v, ref_atual=_ref_decreto(m["dec"], k[4:])) if k.startswith("ind_") else v) for k, v in m["pedidos"].items()}
    # homônimos marcados pelo operador como a mesma pessoa (Auditoria): a tela oferece "Desfazer mesma pessoa"
    m["mesma_pessoa_marcada"] = bool(r.get("_pessoa_man"))
    # regime informado pelo operador não é "como impresso no RSPE"
    if "regime_atual" in (r.get("_manuais") or {}):
        m["regime_rspe"] = ""
    try:
        m["faltas_itens"] = rs.faltas_editaveis(r.get("_incidentes", []), r.get("_eventos", []), rv.HOJE)
    except Exception:
        m["faltas_itens"] = []
    m["_bruto"] = m.pop("_final", None) or r
    return m, migrar


def _ref_decreto(dec, did):
    """Situação de um decreto na aba Indulto ("cabe", "ver", "indeferido"...: o campo s de rd.avaliar), usada como referência
    do pedido "ind_<decreto>" para avisar "situação mudou depois"."""
    x = next((d for d in ((dec or {}).get("decretos") or []) if str(d.get("id")) == str(did)), None)
    return str(x.get("s") or "") if x else ""


def _enc_chave(o):
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return repr(o)


_BJ_DIG = [None, None]


def _bj_digital():
    """Impressão digital da base jurídica carregada (muda se outro base_juridica.json for carregado, mesmo com a mesma versão)."""
    b = getattr(rg, "_BASE", None)
    if _BJ_DIG[0] is not b:
        try:
            _BJ_DIG[1] = hashlib.sha1(json.dumps(b, sort_keys=True, default=_enc_chave, ensure_ascii=False).encode("utf-8")).hexdigest()
        except Exception:
            _BJ_DIG[1] = "%s|%s" % (rg.versao(), id(b))
        _BJ_DIG[0] = b
    return _BJ_DIG[1]


def _chave_calculo(r, sub, hoje):
    """Impressão digital de um cálculo: tudo o que entra em _montar_modelo (o registro, a fatia do contexto, a data de hoje e as
    versões do programa, da leitura da ficha e da base jurídica). Mesma chave = mesmo resultado."""
    h = hashlib.sha1()
    h.update(("%s|%s|%s|%s|" % (VERSAO, rf.VERSAO_LEITURA, _bj_digital(), hoje.isoformat())).encode("utf-8"))
    h.update(json.dumps(r, sort_keys=True, default=_enc_chave, ensure_ascii=False).encode("utf-8"))
    h.update(json.dumps(sub, sort_keys=True, default=_enc_chave, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()


def _ctx_de(ctx, r):
    """Fatia do contexto que interessa a um assistido (o processo paralelo não recebe as tabelas da base inteira)."""
    ch = r.get("processo_execucao") or r.get("arquivo")
    nn = _norm(r.get("nome", ""))
    um = lambda d: {ch: d[ch]} if ch in d else {}
    fichas = {}
    for k in [ch, "nome:" + nn] + list((ctx.get("outros_procs") or {}).get(ch, [])):
        if k in ctx["fichas"]:
            fichas[k] = ctx["fichas"][k]
    if ch not in ctx["fichas"]:
        alt = _ficha_alternativa(ctx["fichas"], r)
        if alt:
            fichas["nome:~alt"] = alt
        else:
            fichas["~cands"] = _fichas_candidatas(ctx["fichas"], r)
    fx = ctx["fixados"]
    return {"baixas": um(ctx["baixas"]), "fichas": fichas, "manuais": um(ctx["manuais"]), "ajustes": um(ctx["ajustes"]),
            "dmanuais": um(ctx["dmanuais"]), "peds": um(ctx["peds"]), "hist_n": um(ctx["hist_n"]),
            "fixados": ({ch: fx[ch]} if ch in fx else {}) if isinstance(fx, dict) else ({ch} if ch in fx else set()),
            "homonimos": {nn: ctx["homonimos"].get(nn, 0)}, "outras_cond": um(ctx.get("outras_cond") or {}), "outros_procs": um(ctx.get("outros_procs") or {}),
            "outras_exec": um(ctx.get("outras_exec") or {}), "homon_det": um(ctx.get("homon_det") or {})}


_CONTEUDO_CRIME = ("processo_criminal", "processo_situacao", "tipo_processo", "data_sentenca", "transito_mp", "transito_processo",
                   "pena_total_processo", "regime_sentenca", "lei", "artigo_rspe", "pena_imposta_rspe", "pena_imposta", "data_infracao", "vga",
                   "resultado_morte", "reincidente_comum", "reincidente_especifico", "fracao_progressao", "fracao_livramento", "extinto_rspe",
                   "suspenso")


_CONTEUDO_BLOCO = ("tipo", "motivo", "complemento", "data", "data_decisao", "data_referencia", "situacao", "processos", "processos_rspe")


def _conteudo_rspe(r):
    """O que o RSPE traz (cabeçalho, cálculo, crimes, eventos e incidentes), sem o que o programa deriva: compara dois RSPEs
    gerados no mesmo dia (o arquivo baixado de novo muda o hash sem mudar o conteúdo)."""
    def _c(c):
        x = {k: c.get(k) or "" for k in _CONTEUDO_CRIME}
        x["pena_imposta"] = c.get("pena_imposta_rspe", c.get("pena_imposta")) or ""
        x.pop("pena_imposta_rspe")
        x["extinto_rspe"] = c.get("extinto_rspe", c.get("extinto")) or ""
        return x
    cab = {k: r.get(k) or "" for k in ("nome", "cpf", "status_execucao", "regime_atual", "pena_total", "pena_cumprida", "pena_remanescente",
                                       "total_interrupcoes", "saldo_remidos", "data_base_seeu", "livramento_data_base_seeu",
                                       "termino_previsao_seeu", "progressao_previsao_seeu", "livramento_previsao_seeu")}
    ev = sorted(json.dumps({k: e.get(k) or "" for k in _CONTEUDO_BLOCO}, sort_keys=True, ensure_ascii=False)
                for e in r.get("_eventos") or [] if not e.get("_ficha"))
    inc = sorted(json.dumps({k: i.get(k) or "" for k in _CONTEUDO_BLOCO}, sort_keys=True, ensure_ascii=False)
                 for i in r.get("_incidentes") or [] if not i.get("_ficha"))
    cr = sorted(json.dumps(_c(c), sort_keys=True, ensure_ascii=False) for c in r.get("_crimes") or [])
    return json.dumps([cab, ev, inc, cr], sort_keys=True, ensure_ascii=False)
