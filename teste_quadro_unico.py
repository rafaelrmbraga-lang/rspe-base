"""Quadro único (7.26): a Execução não tem mais o "Quadro do Usuário" de cada base; "Enviar ao Quadro" grava no Quadro do gabinete
(função Quadro), sem duplicar o mesmo processo e benefício; "pedido feito" na Execução marca a pendência; os cartões antigos de cada
base (não arquivados) são copiados uma vez para o Quadro único, sem apagar as tabelas antigas. Dados fictícios.
Rodar: python teste_quadro_unico.py"""
import os
import sys
import tempfile
import types

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
import rspe_app as app  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


tmp = tempfile.mkdtemp()
api = app.Api.__new__(app.Api)
api._pasta_dados = os.path.join(tmp, "dados")
api._gab = None
api._sei_obj = None
api._cmd = None
eventos = []
api._js = lambda c: eventos.append(c)
api._janela = None

# base com o Quadro do Usuário antigo: dois cartões abertos (um com prazo) e um arquivado
b = app.Base(os.path.join(tmp, "Base Ficticia.sqlite"))
b.con.execute("INSERT INTO assistidos VALUES (?,?,?,?,?,?)", ("7000117-54.2016.8.12.0001", "FULANO DE TAL FICTICIO", "", "", "", "{}"))
b.con.commit()
b.quadro_gravar({"processo": "7000117-54.2016.8.12.0001", "titulo": "Pedir progressão", "obs": "falta atestado", "prazo": "25/11/2026", "aba": "prog", "etiqueta": "urgente"})
b.quadro_gravar({"processo": "", "titulo": "Cobrar a unidade", "obs": "", "prazo": ""})
arq = b.quadro_gravar({"processo": "7000117-54.2016.8.12.0001", "titulo": "Antigo", "obs": "", "prazo": ""})
b.quadro_gravar(dict(next(c for c in b.quadro()["cartoes"] if c["id"] == arq), arquivado="01/11/2026 10:00"))
api.base = b

ok(api.quadro_migrar_base() == 2, "cartões abertos do Quadro do Usuário copiados para o Quadro único")
ok(api.quadro_migrar_base() == 0, "a cópia é feita uma vez só")
P = api._gabinete().lista("pecas")
m = next((x for x in P if x.get("doQuadroDaBase") and x["processo"]), {})
ok(m.get("nome") == "Fulano de Tal Ficticio" and m.get("tipo") == "PROG" and m.get("prazo") == "2026-11-25" and m.get("status") == "pendente"
   and m.get("coluna") == "fazer" and "Pedir progressão" in m.get("obs", "") and "falta atestado" in m.get("obs", "") and m.get("base") == "Base Ficticia",
   "cartão copiado: nome, peça do benefício, prazo, observação e base: %s" % m)
ok(len(b.quadro()["cartoes"]) == 3, "as tabelas antigas da base não foram apagadas")

# Enviar ao Quadro pela Execução: uma pendência por processo e benefício
r = api.quadro_enviar({"processo": "7000999-11.2020.8.12.0001", "nome": "BELTRANA FICTICIA", "aba": "liv", "obs": "Livramento: atingido"})
ok(r.get("ok") and not r.get("ja") and r["peca"]["tipo"] == "LC" and r["peca"]["origem"] == "execucao" and r["peca"]["nome"] == "Beltrana Ficticia",
   "enviado ao Quadro: %s" % r)
ok(api.quadro_enviar({"processo": "7000999-11.2020.8.12.0001", "nome": "BELTRANA FICTICIA", "aba": "liv"}).get("ja"), "não duplica o mesmo processo e benefício")
ok(not api.quadro_enviar({"processo": "7000999-11.2020.8.12.0001", "nome": "BELTRANA FICTICIA", "aba": "prog"}).get("ja"), "outro benefício: outra pendência")
ok(api.quadro_enviar({"processo": "x", "prazo": "31/02"}).get("erro"), "prazo inválido recusado")
ok(any("atdEvento" in e for e in eventos), "a tela do Quadro é avisada")
ok(len(api.quadro_pendencias("70009991120208120001")) == 2, "pendências do processo (por dígitos)")

# pedido feito na Execução marca a pendência do mesmo benefício
ok(api.quadro_pedido_feito("7000999-11.2020.8.12.0001", "liv", "18/11/2026") == 1, "pedido feito marca uma pendência")
liv = next(x for x in api._gabinete().lista("pecas") if x.get("aba") == "liv")
ok(liv.get("etiqueta") == "pedido" and liv.get("pedidoEm") == "2026-11-18" and liv.get("status") == "pendente", "etiqueta Pedido feito: %s" % liv)
b.fechar()
api._gabinete().fechar()
if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: Quadro único (Enviar ao Quadro da Execução sem duplicar, pedido feito, cópia única dos cartões do antigo Quadro do Usuário sem apagar a base)")
