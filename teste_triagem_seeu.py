"""Extensão APTO, Triagem da Mesa do Defensor: roda extensao_seeu_testes/teste_triagem.js no node (leitura da Mesa, do
processo, da lista de arquivos e do texto das decisões; motivo e última decisão; alertas; filtros de final; endereços que a
triagem pode pedir ao SEEU; planilha) e confere a sintaxe dos scripts da triagem. Sem node, só confere que os arquivos
existem."""
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(AQUI, "extensao_seeu")
falhas = []
for f in ("triagem.html", "triagem.js", "triagem_core.js", "pdfjs/pdf.min.mjs", "pdfjs/pdf.worker.min.mjs", "pdfjs/LICENSE.txt"):
    if not os.path.isfile(os.path.join(EXT, f)):
        falhas.append("arquivo %s" % f)
html = open(os.path.join(EXT, "triagem.html"), encoding="utf-8").read()
if '<script src="triagem_core.js"></script>' not in html or '<script type="module" src="triagem.js"></script>' not in html:
    falhas.append("triagem.html carrega triagem_core.js e triagem.js")
js = open(os.path.join(EXT, "triagem.js"), encoding="utf-8").read()
# a página fala com o SEEU pelo content.js; o único pedido direto (PDF que vem do servidor de arquivos do SEEU) passa
# antes pela mesma lista de endereços permitidos
if js.count("fetch(") != 1 or "new XMLHttpRequest" in js or "self.APTO.pedidoTriagemPermitido(abs, metodo, corpo)" not in js:
    falhas.append("triagem.js: um só pedido direto, conferido por pedidoTriagemPermitido")
if js.index("pedidoTriagemPermitido(abs") > js.index("fetch("):
    falhas.append("triagem.js: confere o endereço antes do pedido direto")
if "preAnalise" in js:
    falhas.append("triagem.js não cita o Analisar")
# o pacote do build (zip do Releases e artefato do Actions) leva a pasta da extensão
wf = open(os.path.join(AQUI, ".github", "workflows", "build.yml"), encoding="utf-8").read()
if "Copy-Item -Recurse extensao_seeu pacote\\extensao_seeu" not in wf:
    falhas.append("build.yml: a pasta extensao_seeu entra no pacote")
node = shutil.which("node")
if node:
    r = subprocess.run([node, "--check", os.path.join(EXT, "triagem_core.js")], capture_output=True, text=True)
    if r.returncode:
        falhas.append("sintaxe de triagem_core.js: " + r.stderr.strip())
    with tempfile.TemporaryDirectory() as tmp:
        mjs = os.path.join(tmp, "triagem.mjs")
        shutil.copy(os.path.join(EXT, "triagem.js"), mjs)
        r = subprocess.run([node, "--check", mjs], capture_output=True, text=True)
        if r.returncode:
            falhas.append("sintaxe de triagem.js: " + r.stderr.strip())
    r = subprocess.run([node, os.path.join(AQUI, "extensao_seeu_testes", "teste_triagem.js")], capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(r.stdout)
    if r.returncode:
        falhas.append("teste_triagem.js: " + (r.stderr.strip() or "falhou"))
if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: triagem da Mesa%s" % ("" if node else " - sem node: só os arquivos"))
