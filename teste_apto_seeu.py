"""APTO SEEU (extensão separada, só o painel no SEEU): monta a pasta (ferramentas/apto_seeu/montar.py) e confere o manifesto - permissões
mínimas, só o SEEU e o servidor de arquivos do SEEU, nada de SIAPEN/SEI/SAP/Triagem -, que todo arquivo citado existe e a sintaxe dos
scripts próprios. Sem o motor gerado (ferramentas/motor_extensao/empacotar.py), o teste é pulado. Uso: python teste_apto_seeu.py"""
import json
import os
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "apto_seeu"))
if not os.path.isfile(os.path.join(RAIZ, "extensao_seeu", "motor", "motor.json")):
    print("ok: APTO SEEU - pulado (motor da extensão não gerado)")
    sys.exit(0)
import montar  # noqa: E402

d = montar.montar(tempfile.mkdtemp())
m = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
falhas = []
ok = lambda c, t: c or falhas.append(t)  # noqa: E731
ok(m["manifest_version"] == 3 and m["short_name"] == "APTO SEEU", "manifesto v3, nome APTO SEEU")
ok(sorted(m["permissions"]) == ["offscreen", "storage", "system.display"], "permissões mínimas: %s" % m["permissions"])
ok(m["host_permissions"] == ["https://seeu.pje.jus.br/*", "https://seeu-transfer.s3.sa-east-1.amazonaws.com/*", "https://seeu-transfer.s3.amazonaws.com/*"],
   "só o SEEU e o servidor de arquivos do SEEU: %s" % m["host_permissions"])
ok(len(m["content_scripts"]) == 1 and m["content_scripts"][0]["matches"] == ["https://seeu.pje.jus.br/seeu/*"], "um só script de conteúdo, só no SEEU")
todos = set()
for raiz, _, fs in os.walk(d):
    todos |= {os.path.relpath(os.path.join(raiz, f), d).replace(os.sep, "/") for f in fs}
ok(not [f for f in todos if any(x in f.lower() for x in ("siapen", "sei/", "sap", "triagem", "content.js", "atd_"))], "nada de SIAPEN, SEI, SAP ou Triagem")
citados = list(m["content_scripts"][0]["js"]) + [m["background"]["service_worker"], m["action"]["default_popup"]] + list(m["icons"].values())
citados += [r for w in m["web_accessible_resources"] for r in w["resources"] if "*" not in r]
ok(all(c in todos for c in citados), "todo arquivo citado existe: %s" % [c for c in citados if c not in todos])
ok("motor/motor.json" in todos and "motor/pyodide/pyodide.asm.wasm" in todos and "pdfjs/pdf.min.mjs" in todos, "o motor e o pdf.js vão junto")
for f in ("background.js", "popup.js", "painel/docs_bg.js"):
    r = subprocess.run(["node", "--check", os.path.join(d, f)], capture_output=True, text=True)
    ok(r.returncode == 0, "sintaxe de %s: %s" % (f, r.stderr[:200]))
if falhas:
    print("FALHAS (%d):\n - %s" % (len(falhas), "\n - ".join(falhas)))
    sys.exit(1)
print("ok: APTO SEEU (extensão separada: só o painel no SEEU, permissões mínimas, arquivos completos)")
