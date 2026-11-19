"""APTO SEEU - extensão separada, só com o painel do processo no SEEU (sem SIAPEN, SEI, SAP, Triagem da Mesa nem download do RSPE
para o APTO), para quem vai testar sem a extensão completa do APTO. Monta a pasta a partir dos MESMOS arquivos do painel da
extensão do APTO (extensao_seeu/painel, comum.js, pdfjs, motor) - correção no painel vale para as duas - mais o manifesto, o
service worker e o popup próprios (ferramentas/apto_seeu/fonte).

Uso: python ferramentas/motor_extensao/empacotar.py  (o motor)
     python ferramentas/apto_seeu/montar.py [saida_dir]   -> <saida>/apto_seeu/ e <saida>/apto_seeu_<versão>.zip (com o guia em PDF)"""
import json
import os
import shutil
import sys
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXT = os.path.join(RAIZ, "extensao_seeu")
FONTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonte")
VERSAO = "1.0.0"

PAINEL = ["painel_seeu.js", "painel_core.js", "movs_seeu.js", "previa_seeu.js", "painel.html", "painel.css", "painel.js", "painel_resumo.js",
          "painel_bg.js", "docs_bg.js", "motor.html", "motor.js", "motor_off.js", "pdf_chars.mjs", "previa.html", "previa.js",
          "imprimir.html", "imprimir.js", "SourceSans3-Regular.ttf", "SourceSans3-SemiBold.ttf", "SourceSans3-Bold.ttf"]
SEEU = ["https://seeu.pje.jus.br/*"]
ARQUIVOS = ["https://seeu-transfer.s3.sa-east-1.amazonaws.com/*", "https://seeu-transfer.s3.amazonaws.com/*"]


def manifesto():
    base = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))
    icones = {k: "icones/%s.png" % k for k in ("16", "32", "48", "128")}
    return {
        "manifest_version": 3,
        "name": "APTO SEEU - análise do processo de execução",
        "short_name": "APTO SEEU",
        "version": VERSAO,
        "description": "Na página do processo no SEEU: análise com as regras do APTO (marcos, benefícios, pontos a conferir), chips dos "
                       "marcos, destaques das movimentações e prévia dos documentos. Só leitura; os dados ficam neste computador.",
        "minimum_chrome_version": base.get("minimum_chrome_version", "116"),
        "permissions": ["storage", "offscreen", "system.display"],
        "host_permissions": SEEU + ARQUIVOS,
        "background": {"service_worker": "background.js"},
        "action": {"default_title": "APTO SEEU", "default_popup": "popup.html", "default_icon": {k: v for k, v in icones.items() if k != "128"}},
        "icons": icones,
        "content_security_policy": {"extension_pages": "script-src 'self' 'wasm-unsafe-eval'; object-src 'none'; connect-src 'self' "
                                                       "https://seeu.pje.jus.br https://seeu-transfer.s3.sa-east-1.amazonaws.com "
                                                       "https://seeu-transfer.s3.amazonaws.com"},
        "content_scripts": [{"matches": ["https://seeu.pje.jus.br/seeu/*"], "all_frames": True, "run_at": "document_idle",
                             "js": ["comum.js", "painel/painel_core.js", "painel/painel_seeu.js", "painel/movs_seeu.js", "painel/previa_seeu.js"]}],
        "web_accessible_resources": [{"resources": ["painel/painel.html", "painel/painel.css", "icones/128.png", "painel/previa.html", "painel/previa.js",
                                                    "painel/painel.js", "painel/painel_core.js", "painel/painel_resumo.js", "painel/*.ttf"],
                                      "matches": SEEU}],
    }


def montar(saida):
    if not os.path.isfile(os.path.join(EXT, "motor", "motor.json")):
        raise SystemExit("motor ausente: rode antes python ferramentas/motor_extensao/empacotar.py")
    dst = os.path.join(saida, "apto_seeu")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "painel"))
    for f in PAINEL:
        shutil.copy2(os.path.join(EXT, "painel", f), os.path.join(dst, "painel", f))
    shutil.copy2(os.path.join(EXT, "comum.js"), dst)
    for d in ("pdfjs", "icones", "motor"):
        shutil.copytree(os.path.join(EXT, d), os.path.join(dst, d), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in os.listdir(FONTE):
        shutil.copy2(os.path.join(FONTE, f), dst)
    with open(os.path.join(dst, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifesto(), fh, ensure_ascii=False, indent=2)
    return dst


def zipar(dst, saida, guia=None):
    z = os.path.join(saida, "apto_seeu_%s.zip" % VERSAO)
    if os.path.exists(z):
        os.remove(z)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for raiz, _, fs in os.walk(dst):
            for f in fs:
                p = os.path.join(raiz, f)
                zf.write(p, os.path.join("apto_seeu", os.path.relpath(p, dst)))
        if guia:
            zf.write(guia, os.path.basename(guia))
    return z


if __name__ == "__main__":
    saida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "dist")
    os.makedirs(saida, exist_ok=True)
    d = montar(saida)
    guia = None
    if len(sys.argv) > 2:   # capturas de tela do SEEU fictício (teste_painel_e2e.js) para o guia
        import guia as g
        guia = g.gerar(os.path.join(saida, "APTO_SEEU_guia.pdf"), sys.argv[2], VERSAO)
    print("APTO SEEU %s: %s" % (VERSAO, zipar(d, saida, guia)))
