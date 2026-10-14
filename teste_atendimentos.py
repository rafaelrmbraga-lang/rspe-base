"""Atendimentos por unidade: leitura da "Listagem Internos Ativos" (SIAPEN) e do "Relatório de Atendimento" (SAP) - com o nome
comprido impresso em duas linhas sobrepostas, localização e entrada sem coluna fixa e o relatório lido em blocos -, cruzamento
dos nomes (igual, sem preposição/apóstrofo, cortado; parecido só como aviso), cores de 90 dias, ordem de prioridade, internos
sem RSPE e importação pelo "Importar PDFs". PDFs sintéticos com nomes fictícios."""
import os
import shutil
import sys
import tempfile
import types
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rspe_atendimentos as ratd  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def listagem_pdf(caminho, linhas):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(caminho, pagesize=(612, 792))
    H = 792
    for i, t in enumerate(["GOVERNO DO ESTADO DE MATO GROSSO DO SUL", "AGÊNCIA ESTADUAL DE ADMINISTRAÇÃO DO SISTEMA PENITENCIÁRIO - AGEPEN",
                           "UNIDADE PENAL DE TESTE", "LISTAGEM INTERNOS ATIVOS"]):
        c.setFont("Helvetica", 9)
        c.drawString(150, H - 60 - 12 * i, t)
    for x, t in ((89, "NOME"), (301, "LOCALIZAÇÃO"), (431, "ENTRADA"), (489, "PROCEDÊNCIA")):
        c.drawString(x, H - 160, t)
    y = H - 185
    for n, (nome, extra, resto) in enumerate(linhas, 1):
        c.setFont("Helvetica", 9)
        c.drawString(70 if n < 10 else 65, y, str(n))
        c.drawString(89, y, nome)
        c.drawString(300, y, resto)
        if extra:  # 2ª linha do nome impressa por cima da 1ª, um pouco deslocada (como no SIAPEN)
            c.drawString(89, y - 0.12, extra)
        y -= 11.5
    c.drawString(60, 40, "Projeto SIAP, Impresso em 14/10/2026 - 11:05:38, Pag. 1/1")
    c.save()


def relatorio_pdf(caminho, regs):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(caminho, pagesize=(842, 595))
    H = 595
    c.setFont("Helvetica", 9)
    c.drawString(708, H - 30, "Gerado em : 14/10/2026 10:57")
    c.drawString(94, H - 48, "RELATÓRIO DE ATENDIMENTO")
    c.drawString(94, H - 66, "PERÍODO: 01/01/2026 à 14/10/2026")
    y = H - 105
    for nome, cima, baixo, status, data in regs:
        c.setFont("Helvetica", 8)
        c.drawString(779, y + 4, "DATA")
        for x, t in ((82, "UNIDADE"), (198, "ESTABELECIMENTO PENAL"), (376, "DEFENSOR(A)"), (548, "ASSISTIDO"), (664, "STATUS ATEND. PRESO")):
            c.drawString(x, y, t)
        c.drawString(762, y - 4, "ATENDIMENTO")
        y -= 28
        c.drawString(180, y + 5, "CENTRO PENAL")
        c.drawString(25, y, "NÚCLEO DE TESTE")
        c.drawString(320, y, "Defensora Teste")
        if cima:
            c.drawString(490, y + 5, cima)
            c.drawString(490, y - 5, baixo)
        else:
            c.drawString(490, y, nome)
        c.drawString(659, y, status)
        c.drawString(759, y, data)
        c.drawString(800, y, "10:00")
        c.drawString(180, y - 5, "UNIDADE DE TESTE")
        y -= 30
    c.drawString(60, 40, "TOTAL DE ATENDIMENTOS: %d" % len(regs))
    c.drawString(380, 30, "Página 1 de 1")
    c.save()


tmp = tempfile.mkdtemp()
try:
    LP, RP = os.path.join(tmp, "ListagemdeInternosAtivos_TESTE.pdf"), os.path.join(tmp, "RELATORIO_ATENDIMENTO_TESTE.pdf")
    listagem_pdf(LP, [("FULANO DE TAL", "", "A - UNICO - 001 01/02/2026 EPJFC"),
                      ("BELTRANO SILVA", "", "B - UNICO - 002 03/03/2025 IPCG"),
                      ("CICLANO COSTA E SOUZA", "", "C - UNICO - 003 04/04/2026 PTRAN"),
                      ("JOAO PEDRO DA SILVA", "MOREIRA", "D - UNICO - 104 05/05/2026 EPJFC"),     # nome em duas linhas
                      ("MARCOS PAULO GONCALVES DE", "", "D - UNICO - 105 06/06/2026 EPJFC"),     # cortado pelo SIAPEN
                      ("ALEXANDRO TESTE SANTOS", "", "A - UNICO - 006 07/07/2026 EPJFC"),        # só parecido no SAP
                      ("PEDRO SANT ANA", "", "A - UNICO - 007 08/08/2026 EPJFC"),
                      ("SEM DOCUMENTO NENHUM", "", "A - UNICO - 008 09/09/2026 EPJFC")])
    relatorio_pdf(RP, [("BELTRANO SILVA", "", "", "PRESENCIAL", "10/01/26"),
                       ("BELTRANO SILVA", "", "", "TELEFONE", "02/03/26"),              # o último vale
                       ("CICLANO COSTA SOUZA", "", "", "E-MAIL", "01/10/26"),
                       ("", "JOAO PEDRO DA SILVA", "MOREIRA", "VÍDEO CONFERÊNCIA", "20/09/26"),
                       ("MARCOS PAULO GONÇALVES DE LIMA", "", "", "ANÁLISE PROCESSUAL", "16/07/26"),
                       ("LEANDRO TESTE SANTOS", "", "", "ANÁLISE PROCESSUAL", "11/10/26"),
                       ("PEDRO SANT'ANA", "", "", "PRESENCIAL", "16/07/26"),
                       ("JA SAIU DA UNIDADE", "", "", "PRESENCIAL", "12/10/26")])
    ok(ratd.tipo_do_arquivo(LP) == "listagem" and ratd.tipo_do_arquivo(RP) == "relatorio", "tipos dos PDFs")
    ok(ratd.tipo_pelo_nome("ListagemdeInternosAtivosR6_LOGIN_X.pdf") == "listagem" and ratd.tipo_pelo_nome("RELATORIO_ATENDIMENTO_SEM_FATO_1.pdf") == "relatorio"
       and not ratd.tipo_pelo_nome("0001234-11.2020.8.12.0001.pdf"), "tipos pelo nome do arquivo")
    L = ratd.ler_listagem_arquivo(LP)
    ok(L["unidade"] == "UNIDADE PENAL DE TESTE" and L["emitida"] == "14/10/2026" and len(L["internos"]) == 8, "listagem: %s" % {k: L[k] for k in ("unidade", "emitida")})
    ok(L["internos"][3]["nome"] == "JOAO PEDRO DA SILVA MOREIRA", "nome em duas linhas sobrepostas: %s" % L["internos"][3]["nome"])
    ok(L["internos"][0]["local"] == "A - UNICO - 001" and L["internos"][0]["entrada"] == "01/02/2026" and L["internos"][0]["procedencia"] == "EPJFC",
       "localização, entrada e procedência: %s" % L["internos"][0])
    for proc in (1, 2):
        R = ratd.ler_relatorio(RP, processos=proc)
        ok(R["periodo"] == ["01/01/2026", "14/10/2026"] and R["n"] == 8 and len(R["pessoas"]) == 7, "relatório (%d processo(s)): %s" % (proc, R["n"]))
    b = R["pessoas"][ratd.norm("BELTRANO SILVA")]
    ok(b["n"] == 2 and b["ultimo"] == "2026-03-02" and b["tipo"] == "TELEFONE" and b["defensor"] == "Defensora Teste", "último atendimento: %s" % b)
    ok(ratd.norm("JOAO PEDRO DA SILVA MOREIRA") in R["pessoas"], "nome do relatório em duas linhas")

    HOJE = date(2026, 10, 14)
    regs = [{"id": "p1", "nome": "Beltrano Silva", "proc": "0000001-11.2020.8.12.0001", "ficha_tem": True},
            {"id": "p2", "nome": "Joao Pedro da Silva Moreira", "proc": "0000002-22.2020.8.12.0001", "ficha_tem": False},
            {"id": "p3", "nome": "Alexandra Teste Santos", "proc": "0000003-33.2020.8.12.0001", "ficha_tem": False}]
    X = ratd.cruzar(L, R, regs, [ratd.norm("CICLANO COSTA E SOUZA")], HOJE)
    por = {x["nome"]: x for x in X}
    ok(len(X) == 8 and "JA SAIU DA UNIDADE" not in por, "só quem está na listagem")
    ok(por["FULANO DE TAL"]["cor"] == "vermelho" and por["SEM DOCUMENTO NENHUM"]["cor"] == "vermelho", "sem atendimento no período: vermelho")
    ok(por["BELTRANO SILVA"]["cor"] == "amarelo" and por["BELTRANO SILVA"]["ultimo"] == "02/03/2026", "mais de 90 dias: amarelo")
    ok(por["CICLANO COSTA E SOUZA"]["cor"] == "verde" and por["CICLANO COSTA E SOUZA"]["ficha"] and not por["CICLANO COSTA E SOUZA"]["rspe"],
       "sem preposição: o mesmo nome; ficha sem RSPE achada")
    ok(por["JOAO PEDRO DA SILVA MOREIRA"]["cor"] == "verde" and por["JOAO PEDRO DA SILVA MOREIRA"]["rspe"]
       and por["JOAO PEDRO DA SILVA MOREIRA"]["proc"] == "0000002-22.2020.8.12.0001", "nome em duas linhas: atendimento e RSPE")
    m = por["MARCOS PAULO GONCALVES DE"]
    ok(m["cor"] == "verde" and m["conf"] == "nome cortado" and m["dias"] == 90 and m["nome_sap"].startswith("MARCOS"), "nome cortado pelo SIAPEN (90 dias = verde): %s" % m)
    a = por["ALEXANDRO TESTE SANTOS"]
    ok(a["cor"] == "vermelho" and a["conf"] == "parecido" and "LEANDRO" in a["obs"], "só parecido: continua vermelho, com o aviso: %s" % a)
    ok(not a["rspe"], "RSPE não é ligado por nome só parecido")
    ok(por["PEDRO SANT ANA"]["cor"] == "verde" and por["PEDRO SANT ANA"]["dias"] == 90, "apóstrofo; 90 dias = verde")
    ok([x["cor"] for x in X][:2] == ["vermelho"] * 2 and [x["cor"] for x in X].index("amarelo") < [x["cor"] for x in X].index("verde"), "ordem de prioridade")
    verdes = [x["dias"] for x in X if x["cor"] == "verde"]
    ok(verdes == sorted(verdes, reverse=True), "dentro da cor, do mais antigo ao mais recente")
    ok(ratd.cruzar(L, None, regs, [], HOJE)[0]["cor"] == "cinza", "sem relatório: cinza")
    P = ratd.pendentes(L, regs)
    ok(len(P) == 6 and "BELTRANO SILVA" not in [p["nome"] for p in P], "internos sem RSPE: %d" % len(P))

    # APTO: "Importar PDFs" separa os dois PDFs para Atendimentos; a lista vem com os internos sem RSPE
    sys.modules.setdefault("webview", types.SimpleNamespace(SAVE_DIALOG=1, FOLDER_DIALOG=2, OPEN_DIALOG=0))
    import rspe_app as app  # noqa: E402
    base = app.Base(os.path.join(tmp, "Teste.sqlite"))
    api = app.Api.__new__(app.Api)
    api.base = base
    api._modelos = regs
    av = api._atend_importar_arquivos([LP, RP, os.path.join(tmp, "outro.pdf")])
    ok(len(av) == 3 and "Listagem" in av[0] and "Relatório" in av[1] and "não é a listagem" in av[2], "avisos da importação: %s" % av)
    r = api.atendimentos()
    ok(r["listagem"]["unidade"] == "UNIDADE PENAL DE TESTE" and r["relatorio"]["n"] == 8 and len(r["lista"]) == 8, "atendimentos da base")
    ok(r["cont"].get("vermelho") == 3 and r["docs"]["sem_rspe"] == 6 and r["docs"]["sem_ficha"] == 7, "contagem: %s %s" % (r["cont"], r["docs"]))
    pu = api._pendentes_unidade()
    ok(pu["unidade"] == "UNIDADE PENAL DE TESTE" and pu["total"] == 8 and len(pu["lista"]) == 6, "pendentes para a aba Geral: %d" % len(pu["lista"]))
    # PDF da janela (números, gráficos e lista), com e sem filtro
    pdf = os.path.join(tmp, "Atendimentos.pdf")
    api._janela = types.SimpleNamespace(create_file_dialog=lambda *x, **k: pdf)
    app._abrir = lambda c: None
    r1 = api.atendimentos_pdf("", "")
    ok(r1 and r1.get("caminho") == pdf and os.path.getsize(pdf) > 5000, "PDF dos atendimentos: %s" % r1)
    import pdfplumber
    with pdfplumber.open(pdf) as d:
        txt = "\n".join(pg.extract_text() or "" for pg in d.pages)
    ok("Situação de atendimento" in txt and "Lista em ordem de prioridade" in txt and "FULANO DE TAL" in txt and "UNIDADE PENAL DE TESTE" in txt,
       "conteúdo do PDF")
    r2 = api.atendimentos_pdf("verde", "")
    with pdfplumber.open(pdf) as d:
        txt = "\n".join(pg.extract_text() or "" for pg in d.pages)
    ok(r2 and "Filtro da janela: até 90 dias" in txt and "FULANO DE TAL" not in txt.split("Lista em ordem de prioridade")[-1], "PDF com o filtro da janela")
    base.con.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: atendimentos por unidade (listagem do SIAPEN e relatório do SAP, nomes sobrepostos e cortados, cores de 90 dias, prioridade, internos sem RSPE)")
