"""Decisões 7.15.2 (pareceres P22 a P29, P52, P53 e P57 - S3041, S4004, S4034), frente progressão, livramento e Auditoria.
Casos hipotéticos, dados fictícios. Rodar: python teste_dec_progressao_auditoria.py

P23 unificação pendente: início + lapso (convenção do SEEU), como a progressão refeita
P24 data-base do livramento na nova prisão depois de soltura: "verificar" (5ª Turma; Tema 1457 pendente)
P25 data-base na nova prisão depois de soltura: estimativa pela fração sobre a pena total, "verificar"
P26 peça da detração sem o AgRg no REsp 2.248.958; 6ª Turma e TJMS conferidos
P27 CPF com dígitos trocados, mesma mãe e mesmo nascimento: "verificar - provável erro de digitação"
P28 nascimento divergente: um item só (o da fonte), com o Preencher
P29 1/6 x 16%: diferença entre os lapsos em dias inteiros (15 dias em 6 anos)
S4004 guia sem lançamento, com pena total impressa: "Pena não iniciada" em verificar
S4034 perda de remidos em duplicidade: "verificar", com a ressalva da tese
"""
import copy
import json
import os
import sys
import types
from datetime import date, timedelta

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 27)
AQUI = os.path.dirname(os.path.abspath(__file__))
P1 = "0000001-11.2020.8.12.0001"
AR, PR = "FIXAÇÃO/ALTERAÇÃO DE REGIME", "PRISÃO/INÍCIO DE CUMPRIMENTO"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "6 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_sentenca": "10/06/2021",
         "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não", "vga": "N",
         "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "16% - Art.112, I, da LEP", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado",
         "tipo_processo": "ACAO PENAL"}
    c.update(kw)
    return c


def reg(crimes, incs=(), eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "6a0m0d", "pena_cumprida": "0a3m0d",
         "pena_remanescente": "5a9m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": list(incs), "_eventos": list(eventos), "data_nascimento": "01/01/1980", "status_execucao": "ATIVO",
         "reincidente": "N", "cpf": "", "nome_mae": "MAE FICTICIA"}
    r.update(kw)
    return r


def inc(tipo, compl, dec, ref, sit="CONCEDIDO"):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": dec, "data_referencia": ref, "processos": "", "situacao": sit}


def ev(tipo, motivo, data):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": P1}


def itens(r, tipo=None):
    its = ra.auditar(copy.deepcopy(r), HOJE)["aud_itens"]
    return [i for i in its if tipo is None or i.get("tipo") == tipo]


def caso(arq, cid):
    return next(c for c in json.load(open(os.path.join(AQUI, "casos_simulados", "cobertura", arq), encoding="utf-8")) if c["id"] == cid)


# ---- P23: unificação pendente, início + lapso ----
r = copy.deepcopy(caso("progressao.json", "S3041")["rspe"])
t, d = rv.data_progressao(r)
# 730 x 16% = 116; 3.285 x 25% = 821; 937 dias desde 15/01/2026
ok(d == date(2026, 1, 15) + timedelta(days=937) == date(2028, 8, 9) and "unificação pendente" in t, "P23: %s %s" % (t, d))

# ---- P24 e P25: nova prisão depois de soltura ----
DB = date(2026, 3, 1)
EVS = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2021"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "09/04/2021"),
       ev(PR, "PRISÃO PREVENTIVA", rs.fmt(DB))]
INCS = [inc(AR, "Fechado - Regime Inicial", "10/01/2021", "10/01/2021")]
# custódia anterior: 10/01 a 09/04/2021 = 90 dias; pena 2.190 dias, 16%
# forma gravosa (SEEU): (2.190 - 90) x 16% = 336; favorável: 2.190 x 16% - 90 = 350 - 90 = 260; diferença 90 x 0,84 = 75
gravosa = DB + timedelta(days=336)
r = reg([crime()], INCS, EVS, data_base_seeu=rs.fmt(DB), livramento_data_base_seeu=rs.fmt(DB), progressao_previsao_seeu=rs.fmt(gravosa))
x = itens(r, "data-base-na-nova-prisao-tema-1457")
ok(x and x[0]["nivel"] == "verificar" and rs.fmt(gravosa - timedelta(days=75)) in x[0]["titulo"] and "Tema 1457" in x[0]["detalhe"]
   and "75 dias" in x[0]["detalhe"] and "90 dias" in x[0]["detalhe"], "P25: estimativa pela fração sobre a pena total: %s" % x)
ok(rv.DB_TIPOS.get("data-base-na-nova-prisao-tema-1457", ("",))[0] == "amarelo", "P25: data-base amarela na aba")
# SEEU já pela forma favorável: sem item
r2 = dict(r, progressao_previsao_seeu=rs.fmt(DB + timedelta(days=260)))
ok(not itens(r2, "data-base-na-nova-prisao-tema-1457"), "P25: SEEU já na forma favorável não gera item")
# sem soltura antes (recaptura de fuga): não é o caso
r3 = dict(r, _eventos=[ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2021"), ev("INTERRUPÇÃO", "FUGA", "09/04/2021"), ev(PR, "RECAPTURA", rs.fmt(DB))])
ok(not itens(r3, "data-base-na-nova-prisao-tema-1457"), "P25: recaptura de fuga não é nova prisão depois de soltura")
# P24: data-base do livramento na nova prisão depois de soltura
x = itens(r, "data-base-do-livramento-na-nova-prisao")
ok(x and x[0]["nivel"] == "verificar" and "2.263.217" in x[0]["detalhe"] and "Tema 1457" in x[0]["detalhe"] and "90 dias" in x[0]["detalhe"],
   "P24: livramento na nova prisão: %s" % x)
ok(not itens(r, "data-base-do-livramento-igual-a-da-progressao"), "P24: sem o alerta geral do livramento igual à progressão")
# sem a nova prisão (só progressão): continua o alerta geral
r4 = reg([crime()], INCS + [inc(AR, "Semiaberto - Progressão", "01/03/2023", "01/03/2023")], [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2021")],
         data_base_seeu="01/03/2023", livramento_data_base_seeu="01/03/2023")
ok(itens(r4, "data-base-do-livramento-igual-a-da-progressao") and not itens(r4, "data-base-do-livramento-na-nova-prisao"),
   "P24: progressão sem nova prisão mantém o alerta")

# ---- P26: peça da detração ----
fd = ra.FUND_TIPOS["regime-inicial-depois-da-primeira-prisao"][0]
ok("2.248.958" not in fd and "1.039.806" in fd and "1604202-36.2026.8.12.0000" in fd and "1602525-68.2026.8.12.0000" in fd,
   "P26: peça sem o 2.248.958, com 6ª Turma e TJMS: %s" % fd[-600:])

# ---- P27: CPF com dígitos vizinhos trocados ----
R = {"cpf": "90000002001", "nome": "TESTE FICTICIO", "nome_mae": "MAE FICTICIA", "data_nascimento": "01/01/1975", "_crimes": []}
F = {"cpf": "900.000.002-01", "nome": "TESTE FICTICIO", "nome_mae": "MAE FICTICIA", "filiacao": "MAE FICTICIA \\ PAI FICTICIO",
     "data_nascimento": "01/01/1975"}
x = [i for i in rf._identidade_x_ficha(R, F) if i["titulo"].startswith("CPF da ficha")]
ok(x and x[0]["nivel"] == "verificar" and "provável erro de digitação" in x[0]["titulo"], "P27: mesma mãe e nascimento: %s" % x)
x = [i for i in rf._identidade_x_ficha(R, dict(F, nome_mae="OUTRA MAE", filiacao="OUTRA MAE \\ PAI")) if i["titulo"].startswith("CPF da ficha")]
ok(x and x[0]["nivel"] == "alerta", "P27: mãe diferente mantém o alerta: %s" % x)
x = [i for i in rf._identidade_x_ficha(R, dict(F, cpf="123.456.789-09")) if i["titulo"].startswith("CPF da ficha")]
ok(x and x[0]["nivel"] == "alerta", "P27: CPF bem diferente mantém o alerta: %s" % x)

# ---- P29: 1/6 x 16%, lapsos em dias inteiros ----
r = reg([crime(data_infracao="10/01/2019", fracao_progressao="1/6 - Comum")])
x = [i for i in itens(r, "percentual-de-progressao-diverge") if "16%" in i["titulo"]]
ok(x and "15 dias a mais" in x[0]["titulo"] and x[0].get("dias_diferenca") == 15 and "1/6 = 365 dias; 16% = 350 dias" in x[0]["detalhe"],
   "P29: 2.190 dias - 365 x 350: %s" % x)

# ---- S4004: guia sem lançamento, com pena total ----
r = reg([crime()], pena_cumprida="0a0m0d", regime_atual="")
x = itens(r, "pena-nao-iniciada-seeu")
ok(x and x[0]["nivel"] == "verificar" and "solta" in x[0]["detalhe"], "S4004: verificar: %s" % x)
ok(not itens(r, "pena-interrompida-seeu"), "S4004: sem o info duplicado")
r = reg([crime()], pena_cumprida="0a0m0d", regime_atual="", status_execucao="SUSPENSO")
ok(not itens(r, "pena-nao-iniciada-seeu"), "S4004: execução suspensa fica fora")

# ---- S4034: duplicidade da perda de remidos ----
c = caso("auditoria.json", "S4034")
x = itens(copy.deepcopy(c["rspe"]), "perda-de-dias-remidos-em-duplicidade-falta-de")
ok(x and all(i["nivel"] == "verificar" for i in x) and "não pacífica" in x[0]["detalhe"] and "1604831-44.2025" in x[0]["detalhe"],
   "S4034: verificar com ressalva: %s" % x)

if falhas:
    print("FALHOU: decisões 7.15.2, progressão e Auditoria")
    for f in falhas:
        print("  -", f)
    sys.exit(1)
print("ok: decisões 7.15.2, progressão e Auditoria (unificação pendente, nova prisão depois de soltura e Tema 1457, peça da detração, "
      "CPF com erro de digitação, 1/6 x 16% em dias inteiros, pena não iniciada, duplicidade da perda de remidos)")
