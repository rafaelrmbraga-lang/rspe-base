"""Protótipo do painel sobre a página fictícia do SEEU: o painel é o de verdade (painel.css + painel_core.js) com o resultado
calculado de verdade (leitor das abas + motor do APTO) a partir de um caso simulado. Gera um HTML para abrir no navegador.
Uso: python ferramentas/seeu_ficticio/prototipo.py S035 saida.html [--recolhido] [--aberto-item ID]"""
import json
import os
import subprocess
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import seeu  # noqa: E402
import rspe_painel as rp  # noqa: E402

PAINEL = os.path.join(RAIZ, "extensao_seeu", "painel")


def main():
    cid, saida = sys.argv[1], sys.argv[2]
    casos = {c["id"]: c for c in json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))}
    r = dict(casos[cid]["rspe"], nome="FULANO DE TAL EXEMPLO", nome_mae="MARIA EXEMPLO DA SILVA")
    hoje = sys.argv[sys.argv.index("--hoje") + 1] if "--hoje" in sys.argv else "18/11/2026"
    painel = json.loads(rp.analisar_abas(json.dumps({"abas": seeu.abas_dict(r), "hoje": hoje}, ensure_ascii=False)))
    res = {"estado": "ok", "painel": painel}
    js = ("const C=require(%s);process.stdout.write(C.html(%s))" % (json.dumps(os.path.join(PAINEL, "painel_core.js")), json.dumps(res, ensure_ascii=False)))
    corpo = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout
    css = open(os.path.join(PAINEL, "painel.css"), encoding="utf-8").read().replace("url(", "url(%s/" % PAINEL.replace("\\", "/"))
    html_p = open(os.path.join(PAINEL, "painel.html"), encoding="utf-8").read()
    cont = painel.get("contagem") or {}
    html_p = (html_p.replace('<link rel="stylesheet" href="painel.css">', "<style>%s</style>" % css)
              .replace('<span class="n" id="nome"></span>', '<span class="n" id="nome">%s</span>' % painel.get("nome", ""))
              .replace('<span class="p" id="proc"></span>', '<span class="p" id="proc">%s</span>' % painel.get("processo", ""))
              .replace('<main class="corpo" id="corpo" aria-live="polite"></main>', '<main class="corpo" id="corpo">%s</main>' % corpo)
              .replace('<span class="selo-st verde" id="lg-v"></span>', '<span class="selo-st verde">%d confere</span>' % cont.get("verde", 0))
              .replace('<span class="selo-st amarelo" id="lg-a"></span>', '<span class="selo-st amarelo">%d conferir</span>' % cont.get("amarelo", 0))
              .replace('<script src="painel_core.js"></script>', "").replace('<script src="painel.js"></script>', ""))
    if "--aberto-item" in sys.argv:
        alvo = sys.argv[sys.argv.index("--aberto-item") + 1]
        html_p = html_p.replace("<details><summary>Conta e fundamento", "<details open><summary>Conta e fundamento", 1) if alvo == "1" else html_p
    recolhido = "--recolhido" in sys.argv
    lingueta = ('<button style="position:fixed;right:0;top:38%%;width:38px;background:#1D5A3B;color:#fff;border:0;border-radius:8px 0 0 8px;'
                'padding:10px 0;display:flex;flex-direction:column;align-items:center;gap:8px;box-shadow:-3px 2px 10px rgba(0,0,0,.18);'
                'font:700 12.5px/1 \'Source Sans 3\',system-ui,sans-serif;z-index:9"><span style="writing-mode:vertical-rl;transform:rotate(180deg);'
                'letter-spacing:.12em">APTO</span><span style="background:#fff;color:#765C00;border-radius:10px;font-size:11.5px;padding:2px 5px">'
                '%d</span></button>' % cont.get("amarelo", 0))
    moldura = ('<iframe title="Análise do APTO" style="position:fixed;top:0;right:0;height:100vh;width:392px;border:0;border-left:1px solid #8C9399;'
               'box-shadow:-6px 0 18px rgba(0,0,0,.08)" srcdoc="%s"></iframe>' % html_p.replace("&", "&amp;").replace('"', "&quot;"))
    pag = seeu.pagina(r, "tabInformacoesAdicionais")
    pag = pag.replace("</head>", "<style>html{margin-right:%s}</style></head>" % ("0" if recolhido else "392px"))
    pag = pag.replace("</body>", (lingueta if recolhido else moldura) + "</body>")
    open(saida, "w", encoding="utf-8").write(pag)
    print("ok", saida, cont)


if __name__ == "__main__":
    main()
