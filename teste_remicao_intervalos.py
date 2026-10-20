"""Atestado com período declarado longo e "com intervalos": a tabela mostra os trechos de trabalho da ficha dentro do período
(afastamento e lançamento tornado sem efeito ficam de fora); atestado sem período que não cabe nos trechos inferidos recebe o aviso
de atestado cumulativo; a planilha simples para a petição soma só o que se pode requerer. Dados fictícios.
Rodar: python teste_remicao_intervalos.py"""
import os
import re
import sys
import tempfile
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_export as rx
import rspe_remicao as rr

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
    res = rr.conciliar(r, f, date(2026, 10, 16))
    t14 = next(t for t in res["tabela"] if "014" in t["atestado"])
    pers = [(s["setor"], s["per"]) for s in t14["segs"]]
    ok(len(pers) == 3, "014: trechos %r" % pers)
    ok(any("07/06/2013 a 27/09/2013" in p for _s, p in pers), "014: faxina até o afastamento")
    ok(any("10/06/2015 a 24/06/2015" in p for _s, p in pers), "014: mandioca até o afastamento")
    ok(any("16/11/2015 a 16/12/2015" in p for _s, p in pers), "014: artesanato até a emissão")
    ok(not any("Crina" in s for s, _p in pers), "014: lançamento tornado sem efeito entrou")
    ok("com intervalos" in t14["nota"] and "111 trabalhados declarados" in t14["nota"], "014: nota %r" % t14["nota"])
    ok(all(s.get("vinc") for s in t14["segs"]), "014: trechos sem a marca de vínculo")
    t300 = next(t for t in res["tabela"] if "300" in t["atestado"])
    ok("cumulativo" in t300["nota"] and "posteriores sem origem (65 em 14/11/2011), 187 dias" in t300["nota"], "300: aviso de cumulativo %r" % t300["nota"])
    ok(t300.get("cumulativo") is True and not t14.get("cumulativo"), "marca de cumulativo na tabela")
    ok(t300.get("ja_remido") and "Provavelmente já remido" in t300["rot"] and "122 em 20/04/2010" in t300["nota"], "300: já remido %r / %r" % (t300["rot"], t300["nota"]))
    ok(t14.get("sobreposicao") and "16 dias em 26/11/2014" in t14["nota"], "014: remição sem origem dentro do período %r" % t14["nota"])
    pd = {p_["texto"].split(" de ")[0]: p_ for p_ in res["pendencias"] if p_["status"] in ("NAO_LANCADO", "CUMULATIVO")}
    ok(pd["Atestado 300"]["status"] == "CUMULATIVO" and "requerer a apreciação" not in pd["Atestado 300"]["acao"],
       "pendência do cumulativo %r" % pd.get("Atestado 300"))
    ok("16 dias de 26/11/2014" in pd["Atestado 014/2015"]["acao"] and "requerer o restante" in pd["Atestado 014/2015"]["acao"],
       "pendência com remição sem origem no período %r" % pd.get("Atestado 014/2015"))
    G = rr.agrupar_alertas(res["alertas"] + [{"tipo": "baixa sem início", "texto": "Baixa de Ipcg Faxina da Up em 17/12/2015 sem início registrado na "
                                               "ficha nem vínculo anterior do setor: conferir o período com a unidade.", "data": None},
                                              {"tipo": "capacidade", "texto": "Atestado 300: 600 dias trabalhados não cabem nos períodos inferidos da "
                                               "ficha (40 dias corridos de 10/03/2010 a 20/04/2010) - conferir o período no atestado.", "data": None}], {"300"})
    gl = {g["titulo"]: g for g in G}
    ok("IPCG Faxina da UP: saída em 17/12/2015, sem início registrado" in gl["Trabalho registrado de forma incompleta na ficha"]["itens"]
       and gl["Trabalho registrado de forma incompleta na ficha"]["acao"], "alertas agrupados: baixa sem início %r" % G)
    ok(not any("Atestado 300" in i for g in G for i in g["itens"]), "alerta de capacidade repetido para o cumulativo %r" % G)
    R = res["resumo"]
    ok(R["at_n"] == 2 and R["at_rem"] == 237 and R["at_trab"] == 711 and R["cumulativos"] == 1, "resumo: atestados %r" % R)
    ok(R["homologados"] == 203 and not R["perdidos"], "resumo: homologados %r" % R)
    ok(R["trab_ficha"] > 0 and abs(R["dir_ficha"] - R["trab_ficha"] / 3.0) < 0.01, "resumo: estimativa %r" % R)
    ok("fazendo jus a 237 dias de remição" in R["texto"] and "o sentenciado possui 203 dias remidos" in R["texto"]
       and "insuficientes: faltam cerca de 21 dias" in R["texto"], "resumo: texto %r" % R["texto"])
    ok(not R["estudo"], "resumo: sem estudo na ficha %r" % R["estudo"])
    f2 = dict(f, estudos=[{"curso": "ENSINO FUNDAMENTAL", "inicio": "01.03.2012", "fim": "10.12.2012"}],
              leituras=[{"data": "10.05.2013", "meses": [], "obras": 1, "texto": "RELATÓRIO DE LEITURA"}])
    R2 = rr.conciliar(r, f2, date(2026, 10, 16))["resumo"]
    ok("A ficha indica leitura (relatórios em 10/05/2013) e estudo (de 01/03/2012 a 10/12/2012)" in R2["estudo"]
       and R2["estudo"] in R2["texto"], "resumo: aviso de estudo %r" % R2["estudo"])
    # tabela em Word (para colar na petição)
    import zipfile
    out = os.path.join(tempfile.mkdtemp(), "rem.docx")
    rx.exportar_remicao_tabela({"nome": "Assistido Exemplo", "proc": r["processo_execucao"], "fd_conc": {"tabela": res["tabela"]}, "fd_rem_det": {}}, out)
    z = zipfile.ZipFile(out)
    ok(z.testzip() is None and "word/document.xml" in z.namelist(), "word: pacote")
    import xml.dom.minidom as _md
    xml = z.read("word/document.xml").decode("utf-8")
    _md.parseString(xml)
    txt = re.sub(r"<[^>]+>", "|", xml)
    ok("|37|" in txt.split("Total a requerer", 1)[1], "word: total a requerer")
    ok("Provavelmente já remido" in txt, "word: cumulativo já remido")
    ok("Não lançado no RSPE: requerer, conferindo" in txt, "word: sobreposição")
    ok("cumulativo: fora do total" in txt and "Observações" in txt, "word: aviso do cumulativo e notas")
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
