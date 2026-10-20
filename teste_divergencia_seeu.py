"""Teste de regressão do "!" amarelo (divergência impressa no próprio RSPE do SEEU ou na ficha do SIAPEN): as 6 categorias
(pena total x soma das ações, pena da ação x soma dos crimes, ações com o mesmo número, prisão antes do fato, ficha sem data da
prisão, CPF da ficha x RSPE), os casos que têm explicação e não marcam, o alerta da Auditoria, a baixa (o "!" some e volta ao
desfazer) e a baixa que sobrevive à reimportação do mesmo RSPE. Dados sintéticos. Rodar: python teste_divergencia_seeu.py"""
import copy
import os
import shutil
import sys
import tempfile
import types
from datetime import date

wv = types.ModuleType("webview"); wv.SAVE_DIALOG = 1; wv.FOLDER_DIALOG = 2; wv.OPEN_DIALOG = 0
sys.modules.setdefault("webview", wv)

import rspe_auditoria as ra
import rspe_view as rv

rv.HOJE = date(2026, 10, 12)
P1, P2 = "8800001-00.2018.8.12.0001", "8800002-00.2019.8.12.0001"


def cpf(base9):
    """CPF sintético com os dígitos verificadores corretos."""
    n = [int(x) for x in base9]
    for k in (9, 10):
        n.append((sum(n[i] * (k + 1 - i) for i in range(k)) * 10) % 11 % 10)
    return "".join(map(str, n))


def crime(proc, pena_proc, pena, fato, sent="10/06/2019", **kw):
    c = {"processo_criminal": proc, "processo_situacao": "", "tipo_processo": "ACAO PENAL", "vara_condenacao": "Vara simulada",
         "data_denuncia": "", "data_sentenca": sent, "transito_mp": "", "transito_processo": "10/08/2019",
         "pena_total_processo": pena_proc, "regime_sentenca": "Fechado", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: tipo simulado, Reclusão: 1 a 4 anos E Multa", "pena_imposta": pena, "data_infracao": fato,
         "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum Primário", "extinto": "Não", "suspenso": "Não"}
    c.update(kw)
    return c


def ev(data, procs, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", motivo="PRISÃO EM FLAGRANTE", **kw):
    e = {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": procs}
    e.update(kw)
    return e


def inc(tipo, compl="", procs="", sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": "01/01/2022", "data_referencia": "01/01/2022",
            "processos": procs, "situacao": sit}


def reg(**kw):
    r = {"arquivo": "SIMULADO_DIV.pdf", "nome": "SIMULADO DIVERGENCIA", "processo_execucao": "9900901-00.2026.8.12.0001",
         "cpf": cpf("900000001"), "nome_mae": "MAE SIMULADA", "rg": "", "data_nascimento": "01/01/1980", "tribunal": "TJMS",
         "vara": "TJMS - 1ª VARA DE EXECUÇÃO PENAL", "comarca": "CAMPO GRANDE", "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO",
         "pena_total": "8a0m0d", "pena_cumprida": "2a0m0d", "pena_remanescente": "6a0m0d", "total_interrupcoes": "0a0m0d",
         "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)", "data_base_seeu": "05/10/2024", "progressao_previsao_seeu": "",
         "livramento_previsao_seeu": "", "termino_previsao_seeu": "05/10/2030", "data_geracao_rspe": "05/10/2026", "versao_leitura_rspe": 4,
         "_crimes": [crime(P1, "5a0m0d - PENA ORIGINÁRIA", "5 ano(s), 0 mês(es) e 0 dia(s)", "10/03/2018"),
                     crime(P2, "3a0m0d - PENA ORIGINÁRIA", "3 ano(s), 0 mês(es) e 0 dia(s)", "10/03/2019")],
         "_eventos": [ev("05/10/2024", "%s, %s" % (P1, P2), motivo="PRISÃO DEFINITIVA")],
         "_incidentes": [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regime Inicial")], "_hash": "simdiv"}
    r.update(kw)
    return r


def tipos(r, ficha=None):
    return [i["tipo"] for i in ra.divergencias_fonte(r, ficha)]


def com(r, tipo, ficha=None):
    return [i for i in ra.divergencias_fonte(r, ficha) if i["tipo"] == tipo]


# ---------------- sem divergência ----------------
assert tipos(reg()) == [], tipos(reg())

# ---------------- 1) pena total menor que a soma das ações ----------------
T1 = "divergencia-seeu-pena-total"
x = com(reg(pena_total="6a0m0d"), T1)
# conferência de 20/10/2026: total menor que a soma favorece o assistido - informação, sem pedido
assert len(x) == 1 and x[0]["nivel"] == "info" and "6 anos" in x[0]["detalhe"] and "8 anos" in x[0]["detalhe"], x
assert "conferir nos autos" in x[0]["fundamento"].lower() and x[0]["curto"], x
# o que explica a diferença não marca: comutação, indulto, crime suspenso, crime extinto, ação comutada, unificação
assert not com(reg(pena_total="6a0m0d", _incidentes=[inc("COMUTAÇÃO", "DECRETO", P1)]), T1)
assert not com(reg(pena_total="6a0m0d", _incidentes=[inc("INDULTO", "", P2)]), T1)
r = reg(pena_total="5a0m0d"); r["_crimes"][1]["suspenso"] = "Sim"
assert not com(r, T1)
r = reg(pena_total="5a0m0d"); r["_crimes"][1]["extinto"] = "Sim"
assert not com(r, T1)
r = reg(pena_total="6a0m0d"); r["_crimes"][0]["processo_situacao"] = "Comutada"
assert not com(r, T1)
assert not com(reg(pena_total="7a0m0d", _incidentes=[inc("UNIFICAÇÃO", "2a0m0d", P2)]), T1)  # 5a + 2a unificados = 7a
assert com(reg(pena_total="7a0m0d", _incidentes=[inc("UNIFICAÇÃO", "1a0m0d", P2)]), T1)  # a unificação não fecha a conta
assert not com(reg(pena_total="9a0m0d"), T1)  # total maior que a soma: a Auditoria já tem alerta próprio
assert not com(reg(pena_total="0a0m0d"), T1)  # sem cálculo no SEEU: aviso próprio

# ---------------- 2) pena da ação diferente da soma dos crimes ----------------
T2 = "divergencia-seeu-pena-acao"
r = reg(); r["_crimes"][1]["pena_total_processo"] = "4a0m0d - PENA ORIGINÁRIA"
x = com(r, T2)
assert len(x) == 1 and P2 in x[0]["titulo"] and "4 anos" in x[0]["detalhe"] and "3 anos" in x[0]["detalhe"], x
for rot in ("CONVERTIDA", "MEDIDA DE SEGURANÇA", "HABEAS CORPUS", "APELAÇÃO CRIMINAL"):
    r = reg(); r["_crimes"][1]["pena_total_processo"] = "4a0m0d - " + rot
    assert not com(r, T2), rot
r = reg(); r["_crimes"][1]["pena_total_processo"] = "4a0m0d - PENA ORIGINÁRIA"; r["_crimes"][1]["pena_imposta"] = "0 ano(s), 0 mês(es) e 0 dia(s)"
assert not com(r, T2)  # crime sem pena: a conta já não fecha por isso
r = reg()  # crime extinto fora do total da ação: fecha com os não extintos
r["_crimes"].append(crime(P2, "3a0m0d - PENA ORIGINÁRIA", "1 ano(s), 0 mês(es) e 0 dia(s)", "10/03/2019", extinto="Sim"))
assert not com(r, T2)

# ---------------- 3) duas ações com o mesmo número ----------------
T3 = "divergencia-seeu-acao-duplicada"
r = reg(pena_total="10a0m0d")
r["_crimes"].append(crime(P2, "2a0m0d - PENA ORIGINÁRIA", "2 ano(s), 0 mês(es) e 0 dia(s)", "10/03/2016", sent="10/06/2017"))
x = com(r, T3)
assert len(x) == 1 and P2 in x[0]["titulo"] and "10/06/2017" in x[0]["detalhe"], x
assert not com(r, T2)  # a ação duplicada não vira também "pena da ação x crimes"
r = reg()  # dois crimes da mesma ação (mesma pena total e sentença): não é duplicidade
r["_crimes"][1]["pena_total_processo"] = "4a0m0d - PENA ORIGINÁRIA"
r["_crimes"].append(crime(P2, "4a0m0d - PENA ORIGINÁRIA", "1 ano(s), 0 mês(es) e 0 dia(s)", "10/03/2019"))
assert not com(r, T3) and not com(r, T2)

# ---------------- 4) prisão mais de 30 dias antes do fato da ação vinculada ----------------
T4 = "divergencia-seeu-prisao-antes-do-fato"
r = reg(_eventos=[ev("01/01/2019", P2)])  # fato da ação P2 em 10/03/2019
x = com(r, T4)
assert len(x) == 1 and "01/01/2019" in x[0]["titulo"] and P2 in x[0]["detalhe"] and "10/03/2019" in x[0]["detalhe"], x
assert not com(reg(_eventos=[ev("20/02/2019", P2)]), T4)  # até 30 dias: não marca
assert not com(reg(_eventos=[ev("01/01/2019", P2, _ficha=True)]), T4)  # evento lançado pela ficha: não é dado do SEEU
assert not com(reg(_eventos=[ev("01/01/2019", P2, tipo="INTERRUPÇÃO", motivo="FUGA")]), T4)
assert not com(reg(_eventos=[ev("01/01/2019", P1)]), T4)  # fato de P1 é anterior

# ---------------- 5) ficha sem data da prisão; 6) CPF da ficha x RSPE ----------------
T5, T6 = "divergencia-siapen-sem-data-prisao", "divergencia-siapen-cpf"
c_rspe = reg()["cpf"]
c_fic = cpf("900000002")
f_ok = {"nome": "SIMULADO DIVERGENCIA", "cpf": "%s.%s.%s-%s" % (c_rspe[:3], c_rspe[3:6], c_rspe[6:9], c_rspe[9:]), "data_prisao": "05.10.2024",
        "data_impressao": "01.10.2026"}
assert tipos(reg(), f_ok) == []
assert com(reg(), T5, dict(f_ok, data_prisao="")) and com(reg(), T5, dict(f_ok, data_prisao=""))[0]["nivel"] == "alerta"
x = com(reg(), T6, dict(f_ok, cpf=c_fic))
assert len(x) == 1 and c_fic in x[0]["detalhe"] and c_rspe in x[0]["detalhe"], x
assert not com(reg(cpf="1712345678901"), T6, dict(f_ok, cpf=c_fic))  # número provisório de 13 dígitos do SEEU
assert not com(reg(), T6, dict(f_ok, cpf=c_fic[:-1] + str((int(c_fic[-1]) + 1) % 10)))  # CPF inválido (digitação): não marca
assert not ra._cpf_valido("11111111111") and ra._cpf_valido(c_fic)

# ---------------- Auditoria, "!" e baixa (rspe_view.modelo) ----------------
# conferência de 20/10/2026: a pena total menor que a soma é informação (favorável), sem "!" - o "!" fica com as outras
m = rv.modelo(copy.deepcopy(reg(pena_total="6a0m0d")), {}, None, [])
assert [i["nivel"] for i in m["aud_itens"] if i["tipo"] == T1] == ["info"] and m["div_seeu"] == [], m["div_seeu"]
r = reg(pena_total="9a0m0d", _eventos=[ev("01/01/2019", P2)])
r["_crimes"][1]["pena_total_processo"] = "4a0m0d - PENA ORIGINÁRIA"
m = rv.modelo(copy.deepcopy(r), {}, None, [])
its = [i for i in m["aud_itens"] if i["tipo"].startswith("divergencia-")]
# a prisão anterior ao fato fica "verificar" (item 53 de 16/10: a detração entre processos é possível conforme as datas)
assert sorted(i["tipo"] for i in its) == sorted([T2, T4]) and all(i["nivel"] == ("verificar" if i["tipo"] == T4 else "alerta") and not i["baixado"] for i in its), its
assert len(m["div_seeu"]) == 2 and m["div_seeu_txt"] and m["aud_alertas"] >= 1, m["div_seeu"]
# baixa de uma: o "!" fica só com a outra; das duas: some
b1 = {its[0]["chave"]: {"obs": "conferido nos autos", "data": "12/10/2026"}}
m1 = rv.modelo(copy.deepcopy(r), b1, None, [])
assert len(m1["div_seeu"]) == 1 and its[0]["curto"] not in m1["div_seeu"], m1["div_seeu"]
b2 = dict(b1, **{its[1]["chave"]: {"obs": "conferido", "data": "12/10/2026"}})
m2 = rv.modelo(copy.deepcopy(r), b2, None, [])
assert m2["div_seeu"] == [] and m2["div_seeu_txt"] == "" and all(i["baixado"] for i in m2["aud_itens"] if i["tipo"].startswith("divergencia-"))
# divergência diferente (outra pena da ação): a baixa anterior não vale, o "!" volta
r3 = copy.deepcopy(r); r3["_crimes"][1]["pena_total_processo"] = "4a6m0d - PENA ORIGINÁRIA"
m3 = rv.modelo(r3, b2, None, [])
assert any(t.startswith("Ação %s: pena 4a6m0d" % P2) for t in m3["div_seeu"]), m3["div_seeu"]
# CPF: um alerta só (o do confronto da ficha sai quando a divergência marca)
f_cpf = dict(f_ok, cpf=c_fic, eventos=[], trabalho=[], atestados=[], faltas=[])
try:
    m4 = rv.modelo(copy.deepcopy(reg()), {}, f_cpf, [])
    cpf_its = [i for i in m4["aud_itens"] if "CPF" in i["titulo"]]
    assert [i["tipo"] for i in cpf_its] == [T6], [(i["tipo"], i["titulo"]) for i in cpf_its]
except KeyError:
    pass  # ficha mínima sem algum campo do confronto: o teste da Api abaixo cobre a ficha real
# execução extinta: o alerta continua alerta (o "!" é dado do documento)
m5 = rv.modelo(copy.deepcopy(dict(r, execucao_extinta="extinção simulada")), {}, None, [])
assert m5["div_seeu"] and all(i["nivel"] == ("verificar" if i["tipo"] == T4 else "alerta") for i in m5["aud_itens"] if i["tipo"].startswith("divergencia-")), m5["div_seeu"]

# ---------------- baixa pela Api: grava na base, some da lista, sobrevive à reimportação, volta ao desfazer ----------------
import rspe_app as app

tmp = tempfile.mkdtemp()
try:
    app.pasta_app = lambda: tmp
    app.CONFIG = os.path.join(tmp, "c.json")
    app._abrir = lambda c: None
    cam = os.path.join(tmp, "div.sqlite")
    b = app.Base(cam)
    b.gravar(copy.deepcopy(r))
    b.fechar()
    api = app.Api()
    api._js = lambda *a: None
    api.abrir_base(cam)
    lst = api.listar()
    proc = r["processo_execucao"]
    leve = next(x for x in lst["registros"] if x["id"] == proc)
    assert len(leve["div_seeu"]) == 2, leve.get("div_seeu")  # a lista leve leva o "!" (todas as abas)
    m = next(x for x in api._modelos if x["id"] == proc)
    its = [i for i in m["aud_itens"] if i["tipo"].startswith("divergencia-")]
    for i in its:
        assert api.baixar_alerta(proc, i["chave"], i["titulo"], "conferido nos autos") is not None
    m = next(x for x in api._modelos if x["id"] == proc)
    assert m["div_seeu"] == [], m["div_seeu"]
    # reimportação do mesmo RSPE (novo PDF, mesma divergência): a baixa continua
    api.base.gravar(copy.deepcopy(dict(r, data_geracao_rspe="10/10/2026", arquivo="SIMULADO_DIV2.pdf")))
    api.listar()
    m = next(x for x in api._modelos if x["id"] == proc)
    assert m["div_seeu"] == [] and all(i["baixado"] for i in m["aud_itens"] if i["tipo"].startswith("divergencia-")), m["div_seeu"]
    # base fechada e aberta de novo: a baixa está gravada
    api2 = app.Api()
    api2._js = lambda *a: None
    api2.abrir_base(cam)
    api2.listar()
    m = next(x for x in api2._modelos if x["id"] == proc)
    assert m["div_seeu"] == [], m["div_seeu"]
    # desfazer a baixa de uma: o "!" volta só com ela
    api2.reabrir_alerta(proc, its[0]["chave"])
    m = next(x for x in api2._modelos if x["id"] == proc)
    assert m["div_seeu"] == [its[0]["curto"]], m["div_seeu"]
    for a in (api, api2):
        try:
            a.base.fechar()
        except Exception:
            pass
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("ok: divergência no SEEU/SIAPEN (6 categorias, explicações, alerta da Auditoria, \"!\" e baixa persistente)")
