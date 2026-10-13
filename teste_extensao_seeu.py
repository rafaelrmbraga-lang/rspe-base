"""Extensão "APTO - RSPE do SEEU": manifesto (permissões mínimas, só o domínio do SEEU, sem conexão própria), sintaxe dos
scripts e as funções puras de comum.js (nº CNJ, nome de pasta seguro, caminho do arquivo, endereço aceito, chave do dia).
As funções JS rodam no node, se houver; sem node, só o manifesto é conferido."""
import json
import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(AQUI, "extensao_seeu")
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


m = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))
ok(m["manifest_version"] == 3, "manifesto v3")
ok(sorted(m["permissions"]) == ["downloads", "storage"], "permissões mínimas: %s" % m["permissions"])
ok(m["host_permissions"] == ["https://seeu.pje.jus.br/*"], "só o SEEU: %s" % m["host_permissions"])
ok(all(c["matches"] == ["https://seeu.pje.jus.br/seeu/*"] for c in m["content_scripts"]), "content script só no SEEU")
ok("connect-src 'none'" in m["content_security_policy"]["extension_pages"], "sem conexão de rede própria")
for f in ["background.js", "content.js", "comum.js", "popup.js", "popup.html"] + list(m["icons"].values()):
    ok(os.path.isfile(os.path.join(EXT, f)), "arquivo %s" % f)

node = shutil.which("node")
if node:
    for f in ("background.js", "content.js", "comum.js", "popup.js"):
        r = subprocess.run([node, "--check", os.path.join(EXT, f)], capture_output=True, text=True)
        ok(r.returncode == 0, "sintaxe de %s: %s" % (f, r.stderr.strip()))
    js = r"""
const A = require(process.argv[1]);
const t = (c, m) => { if (!c) { console.log("FALHA: " + m); process.exitCode = 1; } };
t(A.cnj("Processo 0044586-22.2017.8.12.0001 (ATIVO)") === "0044586-22.2017.8.12.0001", "cnj formatado");
t(A.cnj("00445862220178120001") === "0044586-22.2017.8.12.0001", "cnj só dígitos");
t(A.cnj("sem número") === "", "cnj ausente");
t(A.pastaSegura('2ª VEP') === "2ª VEP", "acento e ª mantidos");
t(A.pastaSegura('a/b:c*?"<>|d. ') === "a b c d", "caracteres proibidos: " + A.pastaSegura('a/b:c*?"<>|d. '));
t(A.pastaSegura("CON") === "_CON", "nome reservado");
t(A.pastaSegura("..") === "", "só pontos");
const cfg = { raiz: "APTO", base: "2ª VEP" };
t(A.caminhoArquivo(cfg, "0044586-22.2017.8.12.0001", "2026-10-13") === "APTO/2ª VEP/0044586-22.2017.8.12.0001_2026-10-13.pdf", "caminho com base");
t(A.caminhoArquivo({ raiz: "" , base: "" }, "", "2026-10-13") === "APTO/RSPE_sem_numero_2026-10-13.pdf", "caminho sem base nem nº");
t(A.caminhoArquivo({ raiz: "../x", base: "../../Windows" }, "1", "2026-10-13").indexOf("..") < 0, "sem subir de pasta");
const U = A.urlRspeDoId("100000009157098", "relatorioSituacaoProcessualExecutoriaV2");
t(U === "https://seeu.pje.jus.br/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&report=relatorioSituacaoProcessualExecutoriaV2&idProcessoExecucaoPenal=100000009157098", "endereço do RSPE pelo id");
t(A.urlRspeValida(U), "url do RSPE");
t(!A.urlRspeValida(U.replace("https:", "http:")), "http recusado");
t(!A.urlRspeValida(U.replace("seeu.pje.jus.br", "seeu.pje.jus.br.evil.com")), "outro domínio recusado");
t(!A.urlRspeValida(U.replace("emitirRelatorioSituacaoProcessualExecutoria", "carregarJustificativa")), "outra ação do SEEU recusada");
t(!A.urlRspeValida("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do"), "outra página recusada");
// o link fica dentro do script do SEEU (gerarResaQuadroAcoes com o id; gerarResa com o id numa variável)
const h1 = "function gerarResaQuadroAcoes() { openWindow('/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&report=relatorioSituacaoProcessualExecutoriaV2&idProcessoExecucaoPenal=100000009157098','Visualizar Pdf',600,470); }";
const h2 = 'function gerarResa() { var idProcessoExecucaoPenal = 100000009157098; var acao = "/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=emitirRelatorioSituacaoProcessualExecutoria&report=relatorioSituacaoProcessualExecutoriaV2&idProcessoExecucaoPenal=" + idProcessoExecucaoPenal;';
const h3 = 'var acao = "/seeu/processo/criminal/execucao/processoExecucaoPenal.do?actionType=carregarJustificativa&numeroProcesso=" + numeroProcesso;';
t(JSON.stringify(A.rspeNoHtml(h1)) === JSON.stringify({ id: "100000009157098", report: "relatorioSituacaoProcessualExecutoriaV2" }), "RSPE no script (id no endereço)");
t((A.rspeNoHtml(h2) || {}).id === "100000009157098", "RSPE no script (id na variável)");
t(A.rspeNoHtml(h3) === null, "outra ação não é RSPE");
t(A.ehPdf(new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d])) && !A.ehPdf(new Uint8Array([0x3c, 0x68, 0x74, 0x6d, 0x6c])), "PDF x página");
t(A.chaveDia(cfg, "00445862220178120001", "2026-10-13") === "0044586-22.2017.8.12.0001|2ª VEP|2026-10-13", "chave do dia");
t(/^\d{4}-\d{2}-\d{2}$/.test(A.hojeISO()), "data de hoje");
"""
    r = subprocess.run([node, "-e", js, os.path.join(EXT, "comum.js")], capture_output=True, text=True)
    ok(r.returncode == 0 and "FALHA" not in r.stdout, "funções de comum.js: %s %s" % (r.stdout.strip(), r.stderr.strip()))

# APTO: sem pasta vigiada e com Downloads\APTO criada pela extensão, passa a vigiá-la sozinho (uma vez)
import tempfile
import types
sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
sys.path.insert(0, AQUI)
import rspe_app as app  # noqa: E402
tmp = tempfile.mkdtemp()
antigo = os.environ.get("USERPROFILE")
os.environ["USERPROFILE"] = tmp
try:
    api = app.Api.__new__(app.Api)
    conf = {}
    api._cfg = lambda: dict(conf)
    api._cfg_gravar = lambda **k: conf.update(k)
    api._js = lambda *a: None
    ok(api._vigia_auto() is False and not conf, "sem Downloads\\APTO, nada muda")
    os.makedirs(os.path.join(tmp, "Downloads", "APTO", "2ª VEP"))
    ok(api._vigia_auto() is True and conf.get("pasta_vigiada") == os.path.join(tmp, "Downloads", "APTO") and conf.get("vigiar"),
       "Downloads\\APTO vira a pasta vigiada: %s" % conf)
    conf.clear(); conf["pasta_vigiada"] = "X:\\outra"
    ok(api._vigia_auto() is False and conf["pasta_vigiada"] == "X:\\outra", "pasta escolhida pela pessoa é mantida")
    conf.clear(); conf["vigia_auto_feito"] = True
    ok(api._vigia_auto() is False and "pasta_vigiada" not in conf, "só uma vez (se a pessoa tirou, não volta)")
finally:
    if antigo is None:
        os.environ.pop("USERPROFILE", None)
    else:
        os.environ["USERPROFILE"] = antigo
    shutil.rmtree(tmp, ignore_errors=True)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: extensão do SEEU (manifesto, permissões mínimas, sintaxe, nº do processo, pasta segura, caminho, endereço aceito)%s"
      % ("" if node else " - sem node: só o manifesto"))
