"""Atendimentos do NUSPEN: planilha do lote do SAP (extensão) lida e ligada aos assistidos da base, com a cor e a ordem de
prioridade (nunca atendidos; mais de 90 dias; até 90 dias; sem informação). Dados fictícios."""
import json
import os
import shutil
import sys
import tempfile
import time
import types
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rspe_atendimentos as ratd  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


CSV = ("﻿" + '"Prioridade";"Nome (lista)";"Nome no SAP";"Mãe";"ID SAP";"Último atendimento NUSPEN";"Processo(s)";"Atendimento com o nº";"Situação";"No SEEU"\r\n'
       '"1";"FULANO NUNCA";"";"";"";"sem atendimento registrado";"";"";"não encontrado no SAP";""\r\n'
       '"2";"CICLANO SEM NUSPEN";"CICLANO SEM NUSPEN";"MAE X";"5";"sem atendimento registrado";"";"";"sem atendimento do NUSPEN no SAP";""\r\n'
       '"3";"BELTRANO ANTIGO";"BELTRANO ANTIGO";"MAE Y";"7";"10/01/2026";"0000001-11.2020.8.12.0001";"10/01/2026";"ok";""\r\n'
       '"4";"BELTRANO ANTIGO";"BELTRANO ANTIGO";"MAE Y2";"8";"01/09/2026";"0000001-11.2020.8.12.0001";"01/09/2026";"ok";""\r\n'
       '"5";"JOANA RECENTE";"JOANA RECENTE";"MAE Z";"9";"20/09/2026";"0000002-22.2021.8.12.0001 / 0000003-33.2022.8.12.0001";"20/09/2026";"ok";""\r\n'
       '"6";"MARIA DUPLA";"MARIA DUPLA";"MAE A";"10";"05/05/2026";"";"";"sem nº de processo nos atendimentos do NUSPEN";""\r\n'
       '"7";"MARIA DUPLA";"MARIA DUPLA (USAR ESSE)";"MAE B";"11";"06/06/2026";"";"";"sem nº de processo nos atendimentos do NUSPEN";""\r\n'
       '"8";"PEDRO VELHO";"PEDRO VELHO";"MAE P";"12";"01/02/2025";"";"01/02/2025";"sem nº de processo nos atendimentos do NUSPEN";""\r\n'
       '"9";"ERRO TELA";"";"";"";"";"";"";"a tela do SAP mudou";""\r\n')
cads = ratd.ler_planilha(CSV.encode("utf-8"))
ok(len(cads) == 9, "9 cadastros: %d" % len(cads))
ok(cads[0]["nunca"] and cads[1]["nunca"] and not cads[8]["nunca"], "nunca atendido só com 'não encontrado'/'sem NUSPEN'")
ok(cads[4]["processos"] == ["0000002-22.2021.8.12.0001", "0000003-33.2022.8.12.0001"], "dois nºs na mesma linha")
# planilha da extensão 1.5 (sem "Último atendimento"): vale a data do atendimento
antiga = ratd.ler_planilha('"Nome (lista)";"Nome no SAP";"Mãe";"ID SAP";"Processo(s)";"Data do atendimento";"Situação"\n"X Y";"X Y";"M";"1";"0000009-99.2019.8.12.0001";"15/09/2026";"ok"\n')
ok(antiga[0]["ultimo"] == date(2026, 9, 15), "planilha antiga lida")
try:
    ratd.ler_planilha('"a";"b"\n"1";"2"\n')
    ok(False, "planilha errada recusada")
except ValueError:
    pass

HOJE = date(2026, 10, 14)
regs = [{"id": "a", "nome": "Fulano Nunca", "proc": "1111111-11.2011.8.12.0001"},           # pelo nome: nunca atendido
        {"id": "b", "nome": "Beltrano Antigo", "proc": "0000001-11.2020.8.12.0001"},       # pelo nº: o atendimento mais recente (01/09)
        {"id": "c", "nome": "Joana Recente", "proc": "0000003-33.2022.8.12.0001"},         # 2º nº da linha
        {"id": "d", "nome": "Maria Dupla", "proc": "2222222-22.2012.8.12.0001"},           # homônimos na planilha, sem nº: cinza
        {"id": "e", "nome": "Pedro Velho", "proc": "3333333-33.2013.8.12.0001"},           # pelo nome, mais de 90 dias
        {"id": "f", "nome": "Ciclano Sem Nuspen", "proc": "4444444-44.2014.8.12.0001"},    # nunca atendido
        {"id": "g", "nome": "Fora Da Planilha", "proc": "5555555-55.2015.8.12.0001"},      # cinza
        {"id": "h", "nome": "Erro Tela", "proc": ""}]                                       # não verificado: cinza
L = ratd.classificar(regs, cads, HOJE)
por = {x["id"]: x for x in L}
ok(por["a"]["cor"] == "vermelho" and por["a"]["fonte"] == "nome", "nunca atendido (pelo nome): %s" % por["a"])
ok(por["f"]["cor"] == "vermelho", "sem NUSPEN: vermelho")
ok(por["b"]["cor"] == "verde" and por["b"]["ultimo"] == "01/09/2026" and por["b"]["dias"] == 43, "nº com dois cadastros: o mais recente: %s" % por["b"])
ok(por["c"]["cor"] == "verde" and por["c"]["dias"] == 24, "2º nº da linha")
ok(por["e"]["cor"] == "amarelo" and por["e"]["dias"] > 90, "mais de 90 dias: amarelo")
ok(por["d"]["cor"] == "cinza" and "Homônimos" in por["d"]["txt"], "homônimos sem nº: cinza")
ok(por["g"]["cor"] == "cinza" and por["g"]["txt"] == "Não está na planilha", "fora da planilha: cinza")
ok(por["h"]["cor"] == "cinza" and "Não verificado" in por["h"]["txt"], "não verificado: cinza")
ok([x["id"] for x in L] == ["f", "a", "e", "b", "c", "h", "g", "d"],
   "ordem de prioridade: %s" % [x["id"] for x in L])
# limite dos 90 dias: 90 = verde, 91 = amarelo
c90 = [{"lista": "A B", "nome_sap": "A B", "mae": "", "sap_id": "1", "ultimo": date(2026, 7, 16), "processos": [], "situacao": "", "nunca": False}]
ok(ratd.classificar([{"id": 1, "nome": "A B", "proc": ""}], c90, HOJE)[0]["cor"] == "verde", "90 dias: verde")
c90[0]["ultimo"] = date(2026, 7, 15)
ok(ratd.classificar([{"id": 1, "nome": "A B", "proc": ""}], c90, HOJE)[0]["cor"] == "amarelo", "91 dias: amarelo")
ok(ratd.de_json(json.loads(json.dumps(ratd.para_json(cads))))[2]["ultimo"] == date(2026, 1, 10), "guarda e lê de novo")

# APTO: a planilha que a extensão grava em Downloads\APTO entra sozinha (a mais recente, uma vez) e aparece em Atendimentos
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
import rspe_app as app  # noqa: E402
tmp = tempfile.mkdtemp()
antigo_up, antigo_atd = os.environ.get("USERPROFILE"), app.ATEND_SAP
os.environ["USERPROFILE"] = tmp
app.ATEND_SAP = os.path.join(tmp, "atendimentos_sap.json")
try:
    api = app.Api.__new__(app.Api)
    avisos = []
    api._js = lambda c: avisos.append(c)
    api._modelos = [{"id": r["id"], "nome": r["nome"], "proc": r["proc"]} for r in regs]
    ok(api._atend_auto() is False and api.atendimentos()["tem"] is False, "sem planilha: nada")
    d = os.path.join(tmp, "Downloads", "APTO")
    os.makedirs(d)
    open(os.path.join(d, "SAP_processos_2026-10-13_1000.csv"), "w", encoding="utf-8").write('"Nome (lista)";"Último atendimento NUSPEN";"Situação"\n"X";"01/01/2026";"ok"\n')
    time.sleep(0.05)
    open(os.path.join(d, "SAP_processos_2026-10-14_1000.csv"), "w", encoding="utf-8").write(CSV)
    ok(api._atend_auto() is True and api._atend_auto() is False, "importa a mais recente uma vez")
    r = api.atendimentos()
    ok(r["tem"] and r["arquivo"] == "SAP_processos_2026-10-14_1000.csv" and r["n_planilha"] == 9 and len(r["lista"]) == 8, "atendimentos da base: %s" % {k: r[k] for k in ("arquivo", "n_planilha")})
    ok(r["cont"].get("vermelho") == 2 and r["cont"].get("amarelo") == 1 and r["cont"].get("verde") == 2, "contagem por cor: %s" % r["cont"])
    ok(avisos and "Atendimentos" in avisos[-1], "aviso na tela")
finally:
    for k, v in (("USERPROFILE", antigo_up),):
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    app.ATEND_SAP = antigo_atd
    shutil.rmtree(tmp, ignore_errors=True)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: atendimentos do NUSPEN (planilha do SAP, ligação pelo nº e pelo nome, cores 90 dias, ordem de prioridade, importação sozinha)")
