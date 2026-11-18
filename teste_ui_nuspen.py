"""Telas da gestão do NUSPEN no APTO (7.27), no navegador (node + Playwright), com o PYTHON DE VERDADE por trás: um servidor local
deste teste responde às chamadas da tela com o rspe_nuspen sobre uma base do gabinete temporária (dados fictícios). Confere o fluxo
inteiro pela tela: Quem, providência registrada, prazo, ofício (envio, resposta), cumprimento avaliado e validado, demanda,
inspeção com achado que vira providência, minuta com versões, histórico, relatório e busca. Rodar: python teste_ui_nuspen.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
node = shutil.which("node")
if not node:
    print("ok: (sem node: telas da gestão do NUSPEN não testadas)")
    sys.exit(0)
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
import rspe_app as app  # noqa: E402

api = app.Api.__new__(app.Api)
api._pasta_dados = tempfile.mkdtemp()
api._gab = None
api._sei_obj = None
api._nus_obj = None
api._cmd = None
api._js = lambda c: None
api._janela = None
api.base = None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m = d["m"]
        if m == "sei_importar_pdf":  # a janela de escolher arquivo é do pywebview: aqui vai o PDF fictício do NUSPEN
            r = api.sei_importar_pdf(d["a"][0], [os.path.join(AQUI, "extensao_seeu_testes", "pdfs_nuspen", "processo_t1_ficticio.pdf")])
        else:
            r = api.nus(d["a"][0], d["a"][1]) if m == "nus" else getattr(api, m)(*d["a"]) if m in ("sei_resumo", "sei_processo", "sei_estado") else {}
        b = json.dumps(r, ensure_ascii=False, default=str).encode()
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
try:
    r = subprocess.run([node, os.path.join(AQUI, "extensao_seeu_testes", "teste_ui_nuspen.js"), "http://127.0.0.1:%d" % srv.server_address[1]],
                       capture_output=True, text=True, timeout=300, env=dict(os.environ, NO_PROXY="127.0.0.1", no_proxy="127.0.0.1"))
finally:
    srv.shutdown()
    if api._gab:
        api._gab.fechar()
print((r.stdout or r.stderr).strip()[-3000:])
sys.exit(r.returncode)
