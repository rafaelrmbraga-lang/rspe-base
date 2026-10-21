"""Atestado com período declarado longo e "com intervalos" (modelo da 7.14): cada trecho de trabalho da ficha dentro do período fica
vinculado ao atestado (afastamento e lançamento tornado sem efeito ficam de fora); a comparação soma os atestados; o atestado sem
período emitido a pedido da Promotoria fica sem registro de peticionamento; a tabela em Word traz a comparação, os documentos e o
trabalho x atestados, sem total a requerer. (Até a 7.13: aviso de cumulativo e "provavelmente já remido" pela conciliação, que saiu.)
Dados fictícios.
Rodar: python teste_remicao_intervalos.py"""
import os
import re
import sys
import tempfile
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_export as rx
import rspe_ficha as rf

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


E = lambda d, t: {"data": d, "texto": t}
f = {"data_impressao": "16/10/2026", "eventos": [
    E("10.03.2010", "INICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE ARTESANATO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("20.04.2010", "AFASTADO DO TRABALHO POR FALTA DE PRODUTIVIDADE."),
    E("16.05.2011", "EMITIDO ATESTADO DE TRABALHO Nº 300/11/ST/UPX, CONFORME OFÍCIO DA PROMOTORIA, COM 600 DIAS TRABALHADOS E 200 DIAS REMIDOS."),
    E("07.06.2013", "REINICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE FAXINA DO SOLÁRIO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("27.09.2013", "AFASTADO DO TRABALHO POR FALTA DE PRODUTIVIDADE. CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("20.02.2015", "REINICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE OFICINA DE TRABALHO - BENEFICIAMENTO DE CRINA, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("21.02.2015", "EM TEMPO: TORNAR SEM EFEITO O LANÇAMENTO DO DIA 20/02/2015, REFERENTE AO SETOR DE TRABALHO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("10.06.2015", "REINICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE OFICINA DE TRABALHO - BENEFICIAMENTO DE MANDIOCA, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("24.06.2015", "AFASTADO DO TRABALHO POR FALTA DE PRODUTIVIDADE."),
    E("16.11.2015", "REINICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE OFICINA DE ARTESANATO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
    E("16.12.2015", "FOI EMITIDO ATESTADO DE TRABALHO Nº 014/2015/ST/UPX, ONDE CONSTA 111 DIAS TRABALHADOS E 37 DIAS REMIDOS. COMPREENDENDO O PERIODO DE "
                    "07/06/13 A 16/12/15 (COM INTERVALOS). AUTOS Nº 0000001-11.2010.8.12.0001 - SETOR DE TRABALHO."),
]}
r = {"processo_execucao": "0000001-11.2010.8.12.0001", "_eventos": [{"data": "01/01/2010", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
     "_incidentes": [{"tipo": "REMIÇÃO", "complemento": "65 dias", "data_decisao": "14/11/2011", "data_referencia": "14/11/2011", "situacao": "CONCEDIDO"},
                     {"tipo": "REMIÇÃO", "complemento": "122 dias", "data_decisao": "20/04/2010", "data_referencia": "20/04/2010", "situacao": "CONCEDIDO"},
                     {"tipo": "REMIÇÃO", "complemento": "16 dias", "data_decisao": "26/11/2014", "data_referencia": "26/11/2014", "situacao": "CONCEDIDO"}]}
try:
    rf.atualizar(f)
    o = rf.comparativo(r, f, date(2026, 10, 16))
    N = o["fd_novo"]
    L = [(x["local"], x["periodo"], x["st"], x["at"]) for x in N["trab"]["linhas"]]
    t14 = [x for x in L if x[3] == "014/2015"]
    ok(len(t14) == 3 and all(x[2] == "auto" for x in t14), "014: trechos %r" % L)
    ok(any("07/06/2013 a 27/09/2013" in x[1] for x in t14), "014: faxina até o afastamento")
    ok(any("10/06/2015 a 24/06/2015" in x[1] for x in t14), "014: mandioca até o afastamento")
    ok(any(x[1].startswith("16/11/2015 a 16/12/2015") for x in t14), "014: artesanato até a emissão")
    ok(not any("Crina" in x[0] for x in L), "014: lançamento tornado sem efeito entrou")
    ok(("Artesanato", "10/03/2010 a 20/04/2010", "sem", "") in L, "300 (sem período, anterior ao último período atestado) não é sugerido: %r" % L)
    ok(N["R"]["concedido"] == 203 and N["comp"] == 237 and N["dif"] == 34 and "Verificar remição" in o["fd_sit"], "comparação: %s %s" % (N["comp"], N["dif"]))
    d300 = next(d for d in N["docs"] if d["num"].startswith("300"))
    ok(not d300["pet_ok"] and "Promotoria" in d300["pet"] and d300["sit"] == "Sem registro de peticionamento", "300: %r" % d300)
    # tabela em Word (para colar na petição): comparação, documentos e trabalho x atestados; sem "total a requerer"
    import zipfile
    out = os.path.join(tempfile.mkdtemp(), "rem.docx")
    rx.exportar_remicao_tabela(dict(o, nome="Assistido Exemplo", proc=r["processo_execucao"]), out)
    z = zipfile.ZipFile(out)
    ok(z.testzip() is None and "word/document.xml" in z.namelist(), "word: pacote")
    import xml.dom.minidom as _md
    xml = z.read("word/document.xml").decode("utf-8")
    _md.parseString(xml)
    txt = re.sub(r"<[^>]+>", "|", xml)
    ok("1. Comparação dos totais" in txt and "|237|" in txt and "|+34|" in txt, "word: comparação")
    ok("Atestado de trabalho nº 014/2015" in txt and "Vinculado automaticamente" in txt and "Total a requerer" not in txt, "word: documentos e trabalho")
    ok("não liga remição a atestado" in txt, "word: nota")
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS:")
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok - remição com intervalos e planilha da petição")
