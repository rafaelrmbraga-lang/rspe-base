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
t(A.urlRspeValida("https://seeu.pje.jus.br/seeu/processo/processoExecucaoPenal.do?_tj=1"), "url do RSPE");
t(!A.urlRspeValida("http://seeu.pje.jus.br/seeu/processo/processoExecucaoPenal.do"), "http recusado");
t(!A.urlRspeValida("https://seeu.pje.jus.br.evil.com/seeu/processoExecucaoPenal.do"), "outro domínio recusado");
t(!A.urlRspeValida("https://seeu.pje.jus.br/seeu/visualizacaoProcesso.do"), "outra página recusada");
t(A.chaveDia(cfg, "00445862220178120001", "2026-10-13") === "0044586-22.2017.8.12.0001|2ª VEP|2026-10-13", "chave do dia");
t(/^\d{4}-\d{2}-\d{2}$/.test(A.hojeISO()), "data de hoje");
"""
    r = subprocess.run([node, "-e", js, os.path.join(EXT, "comum.js")], capture_output=True, text=True)
    ok(r.returncode == 0 and "FALHA" not in r.stdout, "funções de comum.js: %s %s" % (r.stdout.strip(), r.stderr.strip()))

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: extensão do SEEU (manifesto, permissões mínimas, sintaxe, nº do processo, pasta segura, caminho, endereço aceito)%s"
      % ("" if node else " - sem node: só o manifesto"))
