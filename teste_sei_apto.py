"""SEI no APTO (7.21), ponta a ponta no laboratório (tudo fictício): o SEI FICTÍCIO do NUSPEN (ferramentas/sei_ficticio), o leitor da
extensão (extensao_seeu/sei, vindo do NUSPEN, rodado no node) e o servidor local do APTO com a base do gabinete. Confere: sem
sessão e escrita barradas, token errado barrado, leitura incremental (a 2ª rodada não relê o que não mudou), documento alterado vira
versão nova (a anterior fica como substituída), obrigações e prazos sugeridos com a frase de origem e sem vencimento calculado,
validar/rejeitar e mandar ao Quadro, e que o SEI fictício nunca recebeu pedido que não fosse GET.
Sem node, só a parte em Python. Rodar: python teste_sei_apto.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, "ferramentas", "sei_ficticio"))
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
import rspe_gabinete as rgab  # noqa: E402
import rspe_sei as rsei  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


tmp = tempfile.mkdtemp()
# ---- regras do NUSPEN aplicadas a um documento (sem servidor) ----
g = rgab.Gabinete(os.path.join(tmp, "g1.sqlite"))
s = rsei.Sei(g)
ses = s.iniciar("todos")["sessao"]
txt = ("DESPACHO\nProcesso nº 99/000123/2026\nTrata-se de inspeção fictícia. Determino a expedição de ofício à direção do EPMF, "
       "com prazo de 30(trinta) dias para resposta. Cumpra-se.")
s.receber_lote(ses, [{"tipo": "processo", "id_sei": "7", "numero": "99/000123/2026", "especificacao": "Inspeção fictícia", "unidade": "NUSPEN"},
                     {"tipo": "documento", "id_sei": "70", "processo": "99/000123/2026", "titulo": "Despacho", "versao": "v1", "conteudo": txt, "hash": rsei.sha(txt)},
                     {"tipo": "documento", "id_sei": "71", "processo": "99/000123/2026", "titulo": "Ofício", "conteudo": "x", "hash": "errado"}])
r = s.resumo()
ok(r["totais"]["processos"] == 1 and r["totais"]["documentos"] == 1 and r["totais"]["falhas"] == 1, "um processo, um documento, hash divergente vira falha: %s" % r["totais"])
p = s.processo(r["processos"][0]["numero"])
o = p["obrigacoes"][0] if p and p["obrigacoes"] else {}
ok(p["documentos"][0]["tipo_codigo"] == "A1", "tipo sugerido: despacho (A1): %s" % p["documentos"][0]["tipo_codigo"])
ok(o.get("status") == "sugestao" and "Determino" in o.get("frase", "") and o.get("prazo_quantidade") == 30 and o.get("prazo_natureza") == "expresso",
   "obrigação sugerida com a frase de origem e prazo expresso de 30 dias: %s" % o)
ok("vencimento" not in json.dumps(o), "prazo sem vencimento calculado")
ok(s.decidir(o["id"], "rejeitada", "")["erro"].startswith("diga o motivo"), "rejeitar pede motivo")
ok(s.decidir(o["id"], "validada").get("ok"), "validar")
h = [x["historico"] for x in s.processo("99/000123/2026")["obrigacoes"] if x["id"] == o["id"]][0]
ok([(x["de"], x["para"]) for x in h] == [("sugestao", "validada")], "decisão no histórico: %s" % h)
# nova versão do documento: a anterior fica (substituída); a obrigação validada fica para conferir
txt2 = txt.replace("30(trinta)", "15(quinze)")
s.receber_lote(ses, [{"tipo": "documento", "id_sei": "70", "processo": "99/000123/2026", "titulo": "Despacho", "versao": "v2", "conteudo": txt2, "hash": rsei.sha(txt2)}])
p = s.processo(p["numero"])
ok(len(p["documentos"]) == 2 and p["documentos"][0]["substituido_por"] == p["documentos"][1]["id"], "versão anterior guardada como substituída")
ok(p["obrigacoes"][0]["status"] == "validada" and "conferir" in (p["obrigacoes"][0]["motivo"] or ""), "obrigação validada da versão anterior fica, para conferir")
ok(p["obrigacoes"][1]["status"] == "sugestao" and p["obrigacoes"][1]["prazo_quantidade"] == 15, "nova versão: nova sugestão (15 dias)")
ok(s.conhecidos(["documento:70", "processo:7", "documento:71"]) == {"documento:70": {"versao": "v2", "hash": rsei.sha(txt2), "ultima_movimentacao": ""},
                                                                    "processo:7": {"versao": "", "hash": "", "ultima_movimentacao": ""}},
   "conhecidos: só o que foi lido bem (falha não conta): %s" % s.conhecidos(["documento:70", "processo:7", "documento:71"]))
# ofício com cabeçalho em linhas sem ponto (como o SEI entrega): a frase da obrigação não leva o cabeçalho junto, e o destinatário é
# o nome e o cargo do bloco "Ao Ilmo. Senhor" (não "Ilmo")
of = ("OFÍCIO Nº 1234/2026/NUSPEN/DPGE-MS\nCampo Grande, 10 de novembro de 2026.\nAo Ilmo. Senhor\nFULANO DE TAL FICTÍCIO\n"
      "Diretor do Estabelecimento Penal Fictício\nAssunto: Inspeção prisional - informações\nSenhor Diretor,\n"
      "Solicito informações sobre o fornecimento de água no estabelecimento, no prazo de 10 (dez) dias.\nAtenciosamente,\nDEFENSOR FICTÍCIO")
s.receber_lote(ses, [{"tipo": "documento", "id_sei": "80", "processo": "99/000123/2026", "titulo": "Ofício", "versao": "v1", "conteudo": of, "hash": rsei.sha(of)}])
ob = [x for x in s.processo("99/000123/2026")["obrigacoes"] if x["frase"].startswith("Solicito") or "Assunto" in x["frase"]]
ok(len(ob) == 1 and ob[0]["frase"].startswith("Solicito informações") and "Assunto" not in ob[0]["frase"], "frase da obrigação sem o cabeçalho: %s" % [x["frase"] for x in ob])
ok(ob and ob[0]["destinatario"] == "FULANO DE TAL FICTÍCIO, Diretor do Estabelecimento Penal Fictício", "destinatário do ofício: %s" % (ob and ob[0]["destinatario"]))
ok(ob and ob[0]["prazo_quantidade"] == 10, "prazo do ofício: 10 dias")
ok(rsei._frases_por_linha("Determino a expedição de ofício\nà direção, com prazo de 5 dias.") == "Determino a expedição de ofício\nà direção, com prazo de 5 dias.",
   "frase que continua na linha de baixo (minúscula) não é cortada")
# indício de resposta (regra do NUSPEN): certidão que cita resposta a ofício; é indício, não cumprimento
cert = "CERTIDÃO\nCertifico que foi juntada a resposta ao ofício nº 1234567, encaminhada pela unidade."
s.receber_lote(ses, [{"tipo": "documento", "id_sei": "82", "processo": "99/000123/2026", "titulo": "Certidão", "versao": "v1", "conteudo": cert, "hash": rsei.sha(cert)}])
dc = [d for d in s.processo("99/000123/2026")["documentos"] if d["id_sei"] == "82"][0]
ok(dc["tipo_codigo"] == "A4" and [x["oficio"] for x in dc["indicios"]] == ["1234567"], "indício de resposta ao ofício 1234567: %s %s" % (dc["tipo_codigo"], dc["indicios"]))
# Visão geral: "entrou desde a última leitura" só a partir da 2ª leitura, comparando com a anterior
s.concluir(ses, {"retrato": [{"id": "7", "numero": "99/000123/2026", "atribuicao": "fulano", "marcadores": [{"nome": "Inspeção"}]}]})
ok(not any(p["entrou_agora"] for p in s.resumo()["processos"]), "1ª leitura: nada para comparar")
ses2 = s.iniciar("todos")["sessao"]
s.concluir(ses2, {"retrato": [{"id": "7", "numero": "99/000123/2026"}, {"id": "9", "numero": "99/000125/2026", "tipo": "Carta", "naoVisualizado": True}]})
rr = {p["original"]: p for p in s.resumo()["processos"]}
ok(rr["99/000125/2026"]["entrou_agora"] and not rr["99/000123/2026"]["entrou_agora"] and rr["99/000125/2026"]["nao_visualizado"] == 1,
   "2ª leitura: o processo novo na lista aparece como entrou agora: %s" % {k: v["entrou_agora"] for k, v in rr.items()})
ses = ses2
# lido antes da 7.26 com acento quebrado (ISO-8859-1 lido como UTF-8): volta a ser desconhecido, para a próxima leitura trazer de novo
ruim = "Of\ufffdcio n\ufffd 3. Solicito informa\ufffd\ufffdes."
s.receber_lote(ses, [{"tipo": "documento", "id_sei": "81", "processo": "99/000123/2026", "titulo": "Of\ufffdcio", "versao": "v1", "conteudo": ruim, "hash": rsei.sha(ruim)}])
ok(s.conhecidos(["documento:81", "documento:80"]).keys() == {"documento:80"}, "documento com acento quebrado é lido de novo; o bom, não")
g.fechar()

# ---- ponta a ponta com o SEI fictício e o servidor do APTO ----
node = shutil.which("node")
if node:
    import servidor as seif  # SEI fictício do NUSPEN
    import rspe_app as app

    srv_sei = seif.criar(0)
    threading.Thread(target=srv_sei.serve_forever, daemon=True).start()
    sei_base = "http://127.0.0.1:%d" % srv_sei.server_address[1]
    api = app.Api.__new__(app.Api)
    api._pasta_dados = os.path.join(tmp, "app")
    api._gab = None
    api._sei_obj = None
    api._cmd = None
    eventos = []
    api._js = lambda c: eventos.append(c)
    api._janela = None
    api.base = None
    api.vigia_info = lambda: {"bases": []}
    app.PORTA_EXTENSAO = 47396
    srv = api._extensao_servidor()
    try:
        rq = urllib.request.Request("http://127.0.0.1:47396/sei/token", headers={"Origin": "chrome-extension://teste"})
        token = json.loads(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(rq, timeout=5).read())["token"]
        # a página da extensão pede o token sem "Origin" (pedido da própria extensão): recebe; página da internet: 403
        r0 = json.loads(urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:47396/sei/token", timeout=5).read())
        ok(r0.get("token") == token, "página da extensão (sem Origin) recebe o token")
        try:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(urllib.request.Request("http://127.0.0.1:47396/sei/token", headers={"Origin": "https://site.qualquer"}), timeout=5)
            ok(False, "token entregue a página da internet")
        except urllib.error.HTTPError as e:
            ok(e.code == 403, "página da internet não recebe o token")
        env = dict(os.environ, SEI_BASE=sei_base, APP_BASE="http://127.0.0.1:47396", TOKEN=token, NO_PROXY="127.0.0.1", no_proxy="127.0.0.1")
        r = subprocess.run([node, os.path.join(AQUI, "extensao_seeu_testes", "teste_sei_e2e.mjs")], capture_output=True, text=True, timeout=600, env=env)
        try:
            j = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            j = {}
            ok(False, "e2e não rodou: %s %s" % (r.stdout[-500:], r.stderr[-1500:]))
        if j:
            ok(j["semSessao"] == "ok", "sem sessão no SEI: para (%s)" % j["semSessao"])
            ok(j["escrita"] == "recusada", "ação de escrita recusada pelo leitor")
            ok(j["tokenErrado"] == "nao_pareado", "token errado barrado: %s" % j["tokenErrado"])
            p1, p2, p3 = j["primeira"], j["repetida"], j["segunda"]
            ok(p1["processos"] == 30 and p1["documentosLidos"] > 60 and p1["novos"] == p1["documentosLidos"] and p1["parada"] == "teto", "1ª leitura: 30 processos: %s" % p1)
            ok(p2["documentosLidos"] == 0 and p2["documentosPulados"] >= p1["documentosLidos"], "2ª leitura igual: nada relido: %s" % p2)
            ok(p3["novos"] + p3["modificados"] >= 1, "SEI mudou: o novo/alterado entra: %s" % p3)
            ok(j["estatisticas"].get("metodos", {}).keys() <= {"GET"}, "o SEI fictício só recebeu GET: %s" % j["estatisticas"].get("metodos"))
            res = api.sei_resumo()
            ok(res["totais"]["processos"] == 30 and res["totais"]["documentos"] >= p1["documentosLidos"], "APTO: processos e documentos: %s" % res["totais"])
            ok(res["totais"]["sugestoes"] > 0, "APTO: obrigações sugeridas pelas regras do NUSPEN: %s" % res["totais"])
            proc = next(x for x in res["processos"] if x["obrigacoes"].get("sugestao"))
            det = api.sei_processo(proc["numero"])
            ob = next(x for x in det["obrigacoes"] if x["status"] == "sugestao")
            ok(ob["frase"] and ob["regra"].startswith(rsei.VERSAO_OBRIGACOES), "fonte: frase e regra versionada")
            ok(api.sei_para_quadro(ob["id"]).get("ok") and api.sei_para_quadro(ob["id"]).get("erro") == "já está no Quadro", "obrigação vai ao Quadro uma vez")
            pc = [x for x in api._gabinete().lista("pecas") if x.get("origem") == "sei"]
            ok(len(pc) == 1 and pc[0]["coluna"] == "fazer" and pc[0]["obs"].startswith(ob["descricao"][:20]), "cartão no Quadro (A fazer): %s" % pc)
            ok(any("ui.seiEvento" in e for e in eventos), "a tela do SEI é avisada")
            # triagem da Mesa do SEEU (a página da extensão manda o resumo): guardada para a função SEEU
            corpo = json.dumps({"triagem": {"quando": 1, "situacao": 1, "linhas": [{"processo": "7000117-54.2016.8.12.0001", "executado": "FULANO FICTICIO"}]}}).encode()
            rq = urllib.request.Request("http://127.0.0.1:47396/seeu/triagem", data=corpo, headers={"Content-Type": "application/json", "Origin": "chrome-extension://teste"})
            ok(json.loads(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(rq, timeout=5).read()).get("ok"), "triagem recebida")
            t = api.seeu_triagem()
            ok(t.get("itens", [{}])[0].get("executado") == "FULANO FICTICIO" and t["itens"][0]["status"] == "aberto" and t.get("recebida"), "intimação guardada para a função SEEU")
            ok(any("ui.seeuEvento" in e for e in eventos), "a tela do SEEU é avisada")
            ok(api.abrir_seeu("https://site.qualquer/").get("erro"), "abrir no SEEU: só o endereço do SEEU")
            # leitor do SEI da Defensoria (páginas sintéticas com a estrutura real) até o APTO
            r2 = subprocess.run([node, os.path.join(AQUI, "extensao_seeu_testes", "teste_sei_dpms_e2e.mjs")], capture_output=True, text=True, timeout=300, env=env)
            try:
                j2 = json.loads(r2.stdout.strip().splitlines()[-1])
            except Exception:
                j2 = {}
                ok(False, "e2e dpms não rodou: %s %s" % (r2.stdout[-500:], r2.stderr[-1500:]))
            if j2:
                ok(j2["semEntrada"] == "sessao_ausente", "SEI da Defensoria sem o Controle de Processos aberto: pede para abrir (%s)" % j2["semEntrada"])
                d1, d2 = j2["primeira"], j2["repetida"]
                ok(d1["processos"] == 3 and d1["documentosLidos"] == 6 and d1["parada"] is None, "SEI da Defensoria: 3 processos, 6 documentos (o anexo PDF fica de fora): %s" % d1)
                ok(d2["documentosLidos"] == 0 and d2["documentosPulados"] == 6, "2ª leitura: nada relido (hash): %s" % d2)
                ok(j2["metodos"] == ["GET"] and set(j2["acoes"]) <= {"procedimento_controlar", "procedimento_trabalhar", "procedimento_visualizar", "documento_visualizar"},
                   "só GET e só as quatro leituras: %s %s" % (j2["metodos"], j2["acoes"]))
                det = api.sei_processo("99/000111/2026")
                ok(det and det["especificacao"].startswith("Inspeção - Unidade Prisional") and det["unidade"] == "NUSPEN-FICT", "processo com tipo, especificação e unidade: %s" % (det and det["especificacao"]))
                ob = [o for o in (det or {}).get("obrigacoes", []) if "Determino" in o["frase"]]
                ok(ob and ob[0]["prazo_quantidade"] == 30, "regras do NUSPEN no texto do SEI da Defensoria: obrigação com prazo de 30 dias")
                # Visão geral: o retrato da lista do Controle (atribuição, marcadores, não visualizado) chega ao APTO
                rp = {p["original"]: p for p in api.sei_resumo()["processos"]}
                p1, p2 = rp.get("99/000111/2026", {}), rp.get("99/000222/2026", {})
                ok(p1.get("atribuicao") == "fulano" and [m["nome"] for m in p1.get("marcadores", [])] == ["Aguardando resposta"] and p1.get("primeiro_visto"),
                   "retrato da lista: atribuição e marcador: %s" % {k: p1.get(k) for k in ("atribuicao", "marcadores", "primeiro_visto")})
                ok(p2.get("nao_visualizado") == 1 and p2.get("tipo") == "Ofício", "não visualizado no SEI e tipo: %s" % {k: p2.get(k) for k in ("nao_visualizado", "tipo")})
    finally:
        if srv:
            srv.shutdown()
            srv.server_close()
        srv_sei.shutdown()
        srv_sei.server_close()
        if api._gab:
            api._gab.fechar()
else:
    print("(sem node: ponta a ponta do SEI não executado)")

if falhas:
    print("FALHA: " + "; ".join(falhas))
    sys.exit(1)
print("ok: SEI no APTO (regras do NUSPEN, versões, validação, conhecidos%s)" % (
    "; ponta a ponta com o SEI fictício: sem sessão/escrita/token errado barrados, leitura incremental, só GET, Quadro" if node else ""))
