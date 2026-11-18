"""SEEU no APTO (7.23): as intimações da Mesa ficam guardadas até a pessoa concluir; "saiu da Mesa" só marca (e só quando a triagem
leu a mesma aba e a mesma situação); a baixa com peça entra na produção do mês e reabrir a tira. Pedidos dos botões Ler a Mesa e Ler
o SEI vão para a aba do sistema. Dados fictícios. Rodar: python teste_seeu_apto.py"""
import os
import sys
import tempfile
import threading
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rspe_gabinete as rgab  # noqa: E402
import rspe_seeu as rseeu  # noqa: E402

falhas = []


def ok(c, m):
    if not c:
        falhas.append(m)


g = rgab.Gabinete(os.path.join(tempfile.mkdtemp(), "g.sqlite"))
s = rseeu.Seeu(g)
L = lambda p, aba="Manifestação", env="01/11/2026", sit=1: {"processo": p, "executado": "FULANO FICTICIO " + p[-4:], "aba": aba, "dataEnvio": env, "situacao": sit,
                                                           "ultimoDia": "25/11/2026", "analise": {"status": "ok", "providencia": {"texto": "Impugnar o cálculo", "urgente": True}}}
r = s.receber({"situacao": 1, "abas": ["Manifestação", "Ciência"], "linhas": [L("7000001-11.2020.8.12.0001"), L("7000002-22.2020.8.12.0001"), L("7000003-33.2020.8.12.0001", "Ciência")]})
ok(r == {"novas": 3, "atualizadas": 0, "sairam": 0}, "1ª triagem: 3 intimações: %s" % r)
# 2ª triagem só da aba Manifestação: a 2 saiu da Mesa; a de Ciência não foi lida (não marca)
r = s.receber({"situacao": 1, "abas": ["Manifestação"], "linhas": [L("7000001-11.2020.8.12.0001")]})
it = {x["processo"]: x for x in s.listar()}
ok(r["sairam"] == 1 and it["7000002-22.2020.8.12.0001"]["foraDaMesa"] and not it["7000003-33.2020.8.12.0001"]["foraDaMesa"], "saiu da Mesa só na aba lida: %s" % r)
ok(all(x["status"] == "aberto" for x in it.values()), "nada sai do APTO sozinho")
# triagem de outra situação não marca as da situação 1
r = s.receber({"situacao": 2, "abas": ["Manifestação"], "linhas": []})
ok(r["sairam"] == 0, "outra situação lida: não marca")
# voltou à Mesa: tira a marca
s.receber({"situacao": 1, "abas": ["Manifestação"], "linhas": [L("7000001-11.2020.8.12.0001"), L("7000002-22.2020.8.12.0001")]})
ok(not {x["processo"]: x for x in s.listar()}["7000002-22.2020.8.12.0001"]["foraDaMesa"], "voltou à Mesa: sem a marca")
k = it["7000002-22.2020.8.12.0001"]["chave"]
ok(s.concluir(k, "MANIF", "")["erro"].startswith("informe a data"), "baixa pede a data")
ok(s.concluir(k, "XX", "18/11/2026")["erro"] == "peça desconhecida", "só as peças do CONTROLE")
r = s.concluir(k, "MANIF", "18/11/2026", "impugnação protocolada")
pc = [p for p in g.lista("pecas") if p.get("origem") == "seeu"]
ok(r.get("ok") and len(pc) == 1 and pc[0]["status"] == "feito" and pc[0]["tipo"] == "MANIF" and pc[0]["feitoEm"] == "2026-11-18", "baixa vira peça feita (conta no mês): %s" % pc)
x = {y["chave"]: y for y in s.listar()}[k]
ok(x["status"] == "concluido" and x["baixa"]["pecaNome"] == "Manifestações" and x["baixa"]["obs"] == "impugnação protocolada", "concluída com a baixa")
s.receber({"situacao": 1, "abas": ["Manifestação"], "linhas": [L("7000001-11.2020.8.12.0001")]})
ok({y["chave"]: y for y in s.listar()}[k]["status"] == "concluido", "concluída continua concluída")
ok(s.concluir(k, "MANIF", "18/11/2026")["erro"] == "já concluída", "não conclui duas vezes")
r = s.reabrir(k)
ok(r["removidas"] == [pc[0]["id"]] and not [p for p in g.lista("pecas") if p.get("origem") == "seeu"], "reabrir tira a peça da produção do mês")
k3 = it["7000003-33.2020.8.12.0001"]["chave"]
ok(s.concluir(k3).get("ok") and not [p for p in g.lista("pecas") if p.get("origem") == "seeu"], "concluir sem baixa não conta")
# nova intimação do mesmo processo (outra data de envio) é outra linha
s.receber({"situacao": 1, "abas": ["Ciência"], "linhas": [L("7000003-33.2020.8.12.0001", "Ciência", "15/11/2026")]})
ok(len([y for y in s.listar() if y["processo"] == "7000003-33.2020.8.12.0001"]) == 2, "intimação nova do mesmo processo: outra linha")

# pedidos dos botões para a aba do SEEU / SEI
c = rgab.Comandos(rgab.TIPOS_SEEU, rgab.AVISO_SEEU, "SEEU")
ok("SEEU não está aberto" in c.pedir("lerMesa", {})["erro"], "sem a aba do SEEU: avisa")
c.visto = time.time()
res = {}
t = threading.Thread(target=lambda: res.update(c.pedir("lerMesa", {})))
t.start()
cmd = None
for _ in range(50):
    cmd = c.proximo()
    if cmd:
        break
    time.sleep(0.05)
ok(cmd and cmd["tipo"] == "lerMesa", "a aba do SEEU pega o pedido")
c.responder(cmd["id"], {"ok": True, "iniciado": True})
t.join(5)
ok(res == {"ok": True, "iniciado": True}, "Ler a Mesa respondido")
cs = rgab.Comandos(rgab.TIPOS_SEI, rgab.AVISO_SEI, "SEI")
ok(cs.pedir("chamarSap", {}).get("erro") == "pedido desconhecido", "a fila do SEI só aceita os pedidos do SEI")
cs.visto = time.time()
t = threading.Thread(target=lambda: res.update(cs.pedir("lerSei", {"modo": "novos", "retomar": 7})))
t.start()
for _ in range(50):
    cmd = cs.proximo()
    if cmd:
        break
    time.sleep(0.05)
ok(cmd and cmd["modo"] == "novos" and cmd["retomar"] == 7, "Ler o SEI leva o modo e a sessão a retomar: %s" % cmd)
cs.responder(cmd["id"], {"ok": True})
t.join(5)
# opções da Mesa conferidas antes de ir para a triagem; planilha da lista
import types  # noqa: E402
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
import rspe_gabinete_api as rga  # noqa: E402
o = rga._opcoes_mesa({"abas": ["5", "9", "2"], "situacao": "7", "etapa": "2", "faixa": "0-2;<x>", "defensores": ["Def"], "tipo": "Cálculo", "prov": "urgente", "outro": 1})
ok(o == {"abas": ["5", "2"], "situacao": "1", "forcar": False, "faixa": "0-2;", "defensores": ["Def"], "tipo": "Cálculo", "prov": "urgente", "busca": "", "etapa": "2"},
   "opções da Mesa conferidas: %s" % o)
import rspe_app as app  # noqa: E402
api = app.Api.__new__(app.Api)
api._pasta_dados = os.path.dirname(g.caminho)
api._gab, api._seeu_obj = g, s
destino = os.path.join(os.path.dirname(g.caminho), "mesa.xlsx")
api._janela = types.SimpleNamespace(create_file_dialog=lambda *a, **k: destino)
r = api.seeu_planilha([x["chave"] for x in s.listar()])
import openpyxl  # noqa: E402
ws = openpyxl.load_workbook(destino).active
ok(r.get("ok") and ws.max_row == len(s.listar()) + 1 and ws["B1"].value == "Processo" and ws["M1"].value == "Situação no APTO", "planilha da Mesa: %s" % r)
api._recurso = staticmethod(lambda n: os.path.join(AQUI, n))
g.fechar()
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: SEEU no APTO (intimações guardadas até concluir, saiu da Mesa só na aba e situação lidas, baixa conta no mês, reabrir tira, "
      "intimação nova é outra linha) e pedidos Ler a Mesa / Ler o SEI")
