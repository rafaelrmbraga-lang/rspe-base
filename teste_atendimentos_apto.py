"""Atendimentos no APTO (7.20): base do gabinete (fila e Fato Narrado do SAP juntados ao atendimento do dia sem apagar o que a
pessoa escreveu; mudanças da tela; backup da extensão antiga), o servidor local para a extensão (só extensões, só JSON) e os
pedidos da tela para a aba do SAP (Chamar, Ver no SAP, Ler a fila). Dados fictícios. Rodar: python teste_atendimentos_apto.py"""
import json
import os
import sys
import tempfile
import threading
import time
import types
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
import rspe_gabinete as rgab  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


tmp = tempfile.mkdtemp()
hoje = rgab.hoje_iso()
g = rgab.Gabinete(os.path.join(tmp, "gabinete.sqlite"))

# ---- fila: cria o atendimento do dia; a 2ª leitura não duplica ----
fila = [{"nome": "FULANO DE TAL FICTICIO (USAR ESTE)", "data": hoje, "hora": "08:30", "rk": "11", "forma": "presencial", "statusSap": "AGUARDANDO"},
        {"nome": "BELTRANA DA SILVA FICTICIA", "data": hoje, "hora": "09:00", "rk": "12", "forma": "virtual"}]
r = g.receber_fila(fila)
ok(r["novos"] == 2 and len(g.lista("atendimentos")) == 2, "fila cria os dois atendimentos: %s" % r)
a = next(x for x in g.lista("atendimentos") if x["rk"] == "11")
ok(a["nome"] == "Fulano de Tal Ficticio" and a["status"] == "agendado" and a["hora"] == "08:30", "nome sem a nota do SAP, em nome próprio: %s" % a["nome"])
b = next(x for x in g.lista("atendimentos") if x["rk"] == "12")
ok(b["nome"] == "Beltrana da Silva Ficticia" and b["forma"] == "virtual", "virtual da fila: %s" % b)
ok(g.receber_fila(fila)["novos"] == 0 and len(g.lista("atendimentos")) == 2, "2ª leitura da fila não duplica")
ok(g.receber_fila(fila)["mudados"] == [], "fila igual: nada a avisar a tela")

# ---- a tela escreve; o SAP lê o Fato Narrado depois: o texto da pessoa fica ----
a["corpo"] = "Foi orientado sobre o cálculo."
a["status"] = "atendido"
a["forma"] = "virtual"
a["formaManual"] = True
g.mudar({"atendimentos": {"upsert": [dict(a)]}})
fato = {"data": "10/11/2026 10:00", "defensor": "Defensor Ficticio", "texto": "Atendimento solicitado. Processo: 0000001-11.2024.8.12.0001",
        "processos": ["0000001-11.2024.8.12.0001"], "contato": "(67) 99999-0000 Maria (mãe)", "quem": "genitora", "virtual": False, "pedido": "saída temporária"}
x = g.receber_fato({"nome": "Fulano de Tal Ficticio", "fato": fato, "forma": "presencial", "fatoLido": "2026-11-18T10:00:00"})
ok(x and x["id"] == a["id"], "Fato Narrado vai para o atendimento do dia (mesmo nome)")
ok(x["corpo"] == "Foi orientado sobre o cálculo." and x["status"] == "atendido", "o texto e a situação escritos ficam")
ok(x["forma"] == "virtual", "forma trocada à mão fica (formaManual)")
ok(x["processos"] == ["0000001-11.2024.8.12.0001"] and x["contato"].startswith("(67)") and x["quem"] == "genitora", "processo, contato e quem vêm do Fato Narrado")
# a tela grava de novo um atendimento sem o fato (cópia antiga): o que veio do SAP não se perde
velho = dict(a)
velho.pop("fato", None)
velho["corpo"] = "Foi orientado sobre o cálculo. Será requerida a progressão."
g.mudar({"atendimentos": {"upsert": [velho]}})
y = next(z for z in g.lista("atendimentos") if z["id"] == a["id"])
ok(y.get("fato") and y["fato"]["pedido"] == "saída temporária" and y["corpo"].endswith("progressão."), "gravação da tela não apaga o Fato Narrado")
# chegada marcada pela recepção (PRESENTE)
g.receber_fila([{"nome": "BELTRANA DA SILVA FICTICIA", "data": hoje, "chegada": "08:52", "statusSap": "PRESENTE"}])
b = next(z for z in g.lista("atendimentos") if z["rk"] == "12")
ok(b["status"] == "presente" and b["chegada"] == "08:52", "chegada marcada no SAP = Presente: %s" % b.get("status"))
ok(g.resumo_dia() == {"total": 2, "lidos": 1, "presentes": 1}, "resumo do dia para o selo: %s" % g.resumo_dia())
# dado da página do SAP é limitado (nada enorme nem campo estranho)
g.receber_fila([{"nome": "X" * 5000, "data": hoje, "forma": "<script>", "outro": "ignorado"}])
z = max(g.lista("atendimentos"), key=lambda q: len(q["nome"]))
ok(len(z["nome"]) <= 300 and z["forma"] == "presencial" and "outro" not in z, "campos da página limitados")
# pendências, ajustes e remoção
g.mudar({"pecas": {"upsert": [{"id": "p1", "tipo": "ST", "status": "pendente", "coluna": "doc", "data": hoje}]}, "ajustes": {hoje + "|HC": 1}})
ok([p["id"] for p in g.lista("pecas")] == ["p1"] and g.kv("ajustes") == {hoje + "|HC": 1}, "pendência e ajuste gravados")
g.mudar({"pecas": {"remover": ["p1"]}})
ok(g.lista("pecas") == [], "pendência removida")
# backup da extensão antiga (Exportar tudo .json): junta sem apagar nem duplicar
bk = {"app": "APTO Atendimentos", "atendimentos": [dict(a), {"id": "zz", "data": "2026-11-01", "nome": "Antigo Ficticio"}], "pecas": [{"id": "p9", "tipo": "HC", "status": "feito", "feitoEm": "2026-11-02"}],
      "ajustes": {"2026-11-03|PP": 2}, "modelos": [{"titulo": "t", "texto": "x"}], "config": {"ordemDia": "nome"}}
ok(g.importar_backup(bk) == 2, "backup: só os 2 registros novos")
ok(g.kv("ajustes")[hoje + "|HC"] == 1 and g.kv("ajustes")["2026-11-03|PP"] == 2 and g.kv("modelos") == [{"titulo": "t", "texto": "x"}], "backup: ajustes somados, frases")
try:
    g.importar_backup({"app": "outro"})
    ok(False, "backup de outro programa deveria falhar")
except ValueError:
    pass
ok(g.copia_do_dia(os.path.join(tmp, "copias")) and os.path.isfile(os.path.join(tmp, "copias", "gabinete %s.sqlite" % hoje)), "cópia do dia")
# pasta do mês do relatório do dia
raiz = os.path.join(tmp, "2. Atendimentos"); os.makedirs(os.path.join(raiz, "1. Outubro"))
ok(os.path.basename(rgab.pasta_do_mes(raiz, 9)) == "1. Outubro", "acha a pasta do mês pelo nome")
ok(os.path.basename(rgab.pasta_do_mes(raiz, 10)) == "2. Novembro", "cria a pasta do mês com o próximo número")

# ---- pedidos da tela para a aba do SAP ----
cmd = rgab.Comandos()
ok("não está aberto" in cmd.pedir("chamarSap", {"nome": "X"}).get("erro", ""), "sem a aba do SAP: avisa na hora")
cmd.visto = time.time()
res = {}
t = threading.Thread(target=lambda: res.update(cmd.pedir("chamarSap", {"nome": "Fulano", "rk": "11"})))
t.start()
c = None
for _ in range(50):
    c = cmd.proximo()
    if c:
        break
    time.sleep(0.05)
ok(c and c["tipo"] == "chamarSap" and c["nome"] == "Fulano" and c["rk"] == "11", "a extensão pega o pedido: %s" % c)
ok(cmd.proximo() is None, "o mesmo pedido não é entregue duas vezes")
cmd.responder(c["id"], {"ok": True})
t.join(5)
ok(res == {"ok": True}, "quem pediu recebe a resposta: %s" % res)
ok(cmd.pedir("apagarTudo", {}).get("erro") == "pedido desconhecido", "só os pedidos de leitura e Chamar")

# ---- servidor local para a extensão ----
import rspe_app as app  # noqa: E402

api = app.Api.__new__(app.Api)
api._pasta_dados = os.path.join(tmp, "app")
api._gab = None
api._cmd = None
api._js = lambda *a: eventos.append(a[0])
api._janela = None
api.base = None
api.vigia_info = lambda: {"bases": []}
api._cfg = lambda: {}
eventos = []
app.PORTA_EXTENSAO = 47398
srv = api._extensao_servidor()
ok(srv is not None, "servidor aberto")


def pedir(caminho, corpo=None, origem="chrome-extension://abc", tipo="application/json"):
    h = {"Content-Type": tipo} if corpo is not None else {}
    if origem:
        h["Origin"] = origem
    rq = urllib.request.Request("http://127.0.0.1:47398" + caminho, data=json.dumps(corpo).encode() if corpo is not None else None, headers=h)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(rq, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None


try:
    st, j = pedir("/atd/fila", {"itens": [{"nome": "CICLANO FICTICIO", "data": hoje, "hora": "10:00"}]})
    ok(st == 200 and j["novos"] == 1 and j["resumo"]["total"] == 1, "extensão entrega a fila: %s %s" % (st, j))
    ok(any("ui.atdEvento" in e and "Ciclano Ficticio" in e for e in eventos), "a tela é avisada do atendimento novo")
    ok(pedir("/atd/fila", {"itens": []}, origem="https://site.qualquer")[0] == 403, "página da internet não grava (403)")
    ok(pedir("/atd/fila", {"itens": []}, origem=None)[0] == 403, "sem origem de extensão não grava (403)")
    ok(pedir("/atd/fila", {"itens": []}, tipo="text/plain")[0] == 403, "só JSON")
    ok(pedir("/atd/outra", {})[0] == 404, "caminho desconhecido: 404")
    st, j = pedir("/atd/fato", {"nome": "Ciclano Ficticio", "fato": None, "fatoLido": "2026-11-18T10:00:00"})
    ok(st == 200 and j["resumo"]["lidos"] == 1, "Fato Narrado (vazio) registrado como lido: %s" % j)
    st, j = pedir("/atd/comando")
    ok(st == 200 and j == {"cmd": None}, "sem pedido: cmd vazio")
    ok(api.atd_tudo()["sap"]["aberto"] is True, "a pergunta da extensão marca o SAP como aberto")
    ok(pedir("/atd/comando", origem="https://site.qualquer")[0] == 403, "página da internet não pega pedidos")
    # arquivos do painel: nada fora das pastas
    ok(api.atd_arquivo("../rspe_app.py").get("erro") == "caminho inválido", "arquivo: sem ..")
    ok("modelos_atendimentos" in api.atd_arquivo("modelos/lista.json").get("erro", ""), "modelos de petição: diz onde pôr a pasta")
    ok(api.atd_arquivo("modelo_docx/word__styles.xml").get("b64"), "modelo do relatório em Word embutido")
    # 7.31.1: a pasta dos modelos é escolhida na tela; sem lista.json, o catálogo sai dos .docx (Fluxo na subpasta "Modelos Fluxo")
    import base64 as _b64, json as _json, tempfile as _tmp
    _m = _tmp.mkdtemp()
    os.makedirs(os.path.join(_m, "Modelos Fluxo"))
    for _a in ("Indulto ficticio.docx", "~$temporario.docx", os.path.join("Modelos Fluxo", "1. Ciencia ficticia.docx"), "nota.txt"):
        open(os.path.join(_m, _a), "wb").write(b"PK")
    _p = api._pastas(); _p["modelos"] = _m; api._gabinete().gravar_kv("pastas_locais", _p)
    _l = _json.loads(_b64.b64decode(api.atd_arquivo("modelos/lista.json")["b64"]).decode("utf-8"))
    ok(sorted((x["nome"], x["grupo"], x["arquivo"]) for x in _l) == [("1. Ciencia ficticia", "Fluxo", "Modelos Fluxo/1. Ciencia ficticia.docx"), ("Indulto ficticio", "Modelos", "Indulto ficticio.docx")],
       "catálogo montado dos .docx da pasta escolhida: %s" % _l)
    ok(api.atd_arquivo("modelos/Modelos Fluxo/1. Ciencia ficticia.docx").get("b64"), "modelo lido da pasta escolhida")
    ok(api.atd_pastas()["modelos"]["efetiva"] == _m, "pasta dos modelos informada à tela")
    api.atd_limpar_pasta("modelos")
    ok(api.atd_abrir_link("https://site.qualquer/x").get("erro"), "só links do WhatsApp")
finally:
    if srv:
        srv.shutdown()
        srv.server_close()
    g.fechar()
    if api._gab:
        api._gab.fechar()

if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: atendimentos no APTO (fila e Fato Narrado juntados sem apagar o escrito, mudanças da tela, backup da extensão, cópia do dia, "
      "pasta do mês, pedidos Chamar/Ler a fila, servidor só para extensões e só JSON)")
