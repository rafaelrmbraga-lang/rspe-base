"""Paridade da leitura da FICHA DISCIPLINAR no navegador com a do APTO: fichas do SIAPEN fictícias em PDF (uma página, várias
páginas, sem histórico, com o histórico antigo oculto em 10 pt e o rodapé em 7 pt) são lidas (1) pelo APTO, com o pdfplumber
(rspe_ficha.extrair) e (2) como na extensão: caracteres pelo pdf.js (node) -> rspe_pdf_paginas -> o mesmo leitor
(rspe_ficha.extrair_paginas_pdf). A ficha e o texto de cada página têm de sair IDÊNTICOS. Uso: python ferramentas/motor_extensao/paridade_ficha.py"""
import json
import os
import subprocess
import sys
import tempfile
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "ferramentas", "seeu_ficticio"))
sys.modules.setdefault("webview", types.ModuleType("webview"))
import ficha_pdf as fp  # noqa: E402
import rspe_ficha as rf  # noqa: E402
import rspe_pdf_paginas as pp  # noqa: E402


def fichas(d):
    evs = []
    for i in range(1, 40):
        m, a = (i % 12) + 1, 2020 + i // 12
        evs.append(("05.%02d.%d" % (m, a), [
            "TRABALHO: Iniciou atividade laboral, no setor de trabalho LIMPEZA, conforme documento CI %d/%d." % (i, a),
            "Emitido ATESTADO DE TRABALHO PRISIONAL Nº %03d/%d; LIMPEZA; DATA INICIAL: 01/%02d/%d; DATA FINAL: 28/%02d/%d; DIAS TRABALHADOS: 25; DIAS REMIDOS: 8." % (i, a, m, a, m, a),
            "SAÍDA TEMPORÁRIA: saiu em saída temporária conforme decisão judicial, retornou no prazo.",
            "Classificado conduta disciplinar em ÓTIMA."][i % 4]))
    return [fp.gerar(os.path.join(d, "f1.pdf"), eventos=fp.EXEMPLO),
            fp.gerar(os.path.join(d, "f2.pdf"), nome="BELTRANO FICTICIO DE SOUZA", cpf="111.222.333-44", filiacao="ANA FICTICIA \\ PEDRO",
                     nascimento="15/07/1985", prisao="10/01/2020", entrada="12/01/2020", conduta="ÓTIMA", eventos=evs, impresso="01/11/2026"),
            fp.gerar(os.path.join(d, "f3.pdf"), nome="CICLANO SEM HISTORICO", eventos=[], oculto=False, impresso="20/08/2026"),
            fp.gerar(os.path.join(d, "f4.pdf"), nome="JOÃO DA CONCEIÇÃO ÁVILA", eventos=fp.EXEMPLO[:2] + [("01.02.2026", "FUGA: evadiu-se da unidade, recapturado em 10/02/2026. Instaurado PADIC.")])]


def main():
    d = tempfile.mkdtemp()
    pdfs = fichas(d)
    args = []
    for p in pdfs:
        args += [p, p[:-4] + ".json"]
    subprocess.run(["node", os.path.join(RAIZ, "ferramentas", "motor_extensao", "pdf_chars_node.mjs")] + args, check=True)
    difs = 0
    for p in pdfs:
        a = rf.extrair(p)
        b = rf.extrair_paginas_pdf(pp.paginas(json.load(open(p[:-4] + ".json", encoding="utf-8"))), p)
        ja, jb = (json.dumps(x, sort_keys=True, ensure_ascii=False, default=str) for x in (a, b))
        import pdfplumber
        with pdfplumber.open(p) as doc:
            ta = [x.extract_text() for x in doc.pages]
        tb = [x.extract_text() for x in pp.paginas(json.load(open(p[:-4] + ".json", encoding="utf-8")))]
        if ta != tb:
            difs += 1
            print("TEXTO DIFERENTE", os.path.basename(p))
        elif ja != jb:
            difs += 1
            print("DIFERENTE", os.path.basename(p), [k for k in a if json.dumps(a[k], default=str) != json.dumps(b.get(k), default=str)])
    print("ficha disciplinar: %d/%d PDFs com a mesma leitura no pdf.js (navegador) e no pdfplumber (APTO)" % (len(pdfs) - difs, len(pdfs)))
    difs += rspes(d)
    difs += alternativas(d)
    sys.exit(1 if difs else 0)


def alternativas(d):
    """Relatório de pena alternativa (fictício): mesmo texto de página e mesma avaliação do cumprimento pelos dois caminhos."""
    import pdfplumber
    import alternativa_pdf
    import rspe_alternativa as ralt
    from datetime import date
    p = alternativa_pdf.gerar(os.path.join(d, "alternativa.pdf"))
    subprocess.run(["node", os.path.join(RAIZ, "ferramentas", "motor_extensao", "pdf_chars_node.mjs"), p, p[:-4] + ".json"], check=True)
    with pdfplumber.open(p) as doc:
        ta = [x.extract_text() or "" for x in doc.pages]
    tb = [x.extract_text() or "" for x in pp.paginas(json.load(open(p[:-4] + ".json", encoding="utf-8")))]
    hoje = date(2026, 3, 15)
    ok = ta == tb and ralt.avaliar(ralt.ler(ta), hoje) == ralt.avaliar(ralt.ler(tb), hoje) and ralt.ler(ta)["medidas"]
    print("pena alternativa: %s" % ("o mesmo texto e a mesma avaliação no pdf.js e no pdfplumber" if ok else "DIFERENTE"))
    return 0 if ok else 1


def rspes(d):
    """RSPE em PDF (fictício, de casos simulados): o texto das páginas pelo pdf.js tem de ser o do pdfplumber e o painel
    (rspe_painel.analisar_rspe) tem de sair com a mesma assinatura pelos dois caminhos."""
    import pdfplumber
    import rspe_painel as rp
    import rspe_pdf
    import rspe_seeu_abas as ra
    import seeu
    casos = json.load(open(os.path.join(RAIZ, "casos_simulados", "casos.json"), encoding="utf-8"))
    pdfs, args = [], []
    for c in casos[::12]:
        texto, _ = ra.montar_texto(seeu.abas_dict(c["rspe"]), "12/10/2026")
        p = rspe_pdf.gerar(os.path.join(d, "rspe_%s.pdf" % c["id"]), texto)
        pdfs.append(p)
        args += [p, p[:-4] + ".json"]
    subprocess.run(["node", os.path.join(RAIZ, "ferramentas", "motor_extensao", "pdf_chars_node.mjs")] + args, check=True)
    difs = 0
    for p in pdfs:
        chars = json.load(open(p[:-4] + ".json", encoding="utf-8"))
        with pdfplumber.open(p) as doc:
            ta = [x.extract_text() or "" for x in doc.pages]
        a = json.loads(rp.analisar_rspe(json.dumps({"textos": ta, "hoje": "12/10/2026"})))
        b = json.loads(rp.analisar_rspe(json.dumps({"paginas": chars, "hoje": "12/10/2026"})))
        if ta != [x.extract_text() or "" for x in pp.paginas(chars)] or a.get("erro") or a.get("assinatura") != b.get("assinatura"):
            difs += 1
            print("RSPE DIFERENTE", os.path.basename(p), a.get("erro"), b.get("erro"))
    print("RSPE: %d/%d PDFs com o mesmo texto e o mesmo painel no pdf.js (navegador) e no pdfplumber (APTO)" % (len(pdfs) - difs, len(pdfs)))
    return difs


if __name__ == "__main__":
    main()
