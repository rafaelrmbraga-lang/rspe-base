"""Leitura robusta do RSPE do SEEU e da Ficha do SIAPEN (13/10/2026), com textos sintéticos (sem dados reais): variações de
impressão e de layout não derrubam a importação. RSPE sem o título, com cabeçalho/rodapé do navegador ("Imprimir / Salvar como
PDF"), título em outra linha, tribunal na linha do "PODER JUDICIÁRIO", sem acentos e com outro rodapé dá o mesmo resultado
jurídico; seção que falha (exceção) vira leitura PARCIAL com a seção afetada, sem derrubar o arquivo; documento que não é RSPE
(atestado, petição, PDF sem texto, protegido por senha) é recusado com o motivo. Rodar: python teste_leitura_robusta.py"""
import os
import sys
import tempfile
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf  # noqa: E402
import rspe_scraper as rs  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)
    return cond


TIT = "RELATÓRIO DA SITUAÇÃO PROCESSUAL EXECUTÓRIA"
CAB = ["PODER JUDICIÁRIO", "TJMS - COMARCA DE CIDADE FICTÍCIA", "1ª VARA DE EXECUÇÃO PENAL DE CIDADE FICTÍCIA", TIT]
PAG1 = """PROCESSO DE EXECUÇÃO
Número Único: 0000001-11.2020.8.12.0001 (ATIVO)
Número Antigo:
Nome: FULANO DE TAL
CPF: 00000000000
RG: 1234567
Nome da Mãe: MARIA DE TAL
Data de Nascimento: 01/01/1990
CÁLCULOS DA PENA:
Regime Atual: Fechado - ATIVO
Pena Total Imposta: 6a0m0d
Pena Cumprida Até Data Atual: 2a0m0d
Pena Remanescente: 4a0m0d
Total Interrupções: 0a0m0d
Saldo dias Remidos: 10 dias (10 dias remidos - 0 dias perdidos)
TÉRMINO DE PENA
Data prevista para o Término da Pena: 01/03/2030
CÁLCULOS PARA PROGRESSÃO DE REGIME:
Data-base adotada no cálculo para progresso regime: 01/03/2024
Comum (1/6): 0a8m0d
Data prevista para progressão de regime: 01/11/2026
CÁLCULOS PARA LIVRAMENTO CONDICIONAL:
Data-base adotada no cálculo para livramento condicional: 01/03/2024
Comum Primário (1/3): 2a0m0d
Data prevista livramento condicional: 01/03/2026
GRÁFICO REPRESENTATIVO DA PENA PRIVATIVA DE LIBERDADE
PROCESSOS CRIMINAIS
Número: 0000002-22.2019.8.12.0001
Tipo: ACAO PENAL
Juízo/Vara de condenação: 1ª Vara Criminal de Cidade Fictícia
Data do recebimento da denúncia: 01/06/2019
Data da Sentença: 01/02/2020
Data do trânsito em julgado do Ministério Público: 01/03/2020
Data do trânsito em julgado do processo: 01/03/2020
Observação:
SENTENÇA/ACÓRDÃO/RECURSO (ATIVO)
Pena total: 6a0m0d - PENA PRIVATIVA DE LIBERDADE
Regime imposto na sentença/acórdão:Fechado"""
PAG2 = """DESMEMBRAMENTO(S)
Lei: 2848/40 - Código Penal
Artigo da Lei: ART 157: Roubo
Pena:CAPUT: Subtrair coisa móvel alheia, para si ou para outrem, mediante grave ameaça ou violência a pessoa, Reclusão: 4 a 10 anos
Pena Imposta: 6 ano(s), 0 mês(es) e 0 dia(s)
Data da infração: 01/05/2019 Violência ou grave ameaça: S Resultado morte: N
Reincidente comum:N Reincidente específico: N
Condenado por exercer comando de organização criminosa:N
Fração adotada no cálculo para progressão de regime: 1/4 - Primário com violência
Fração adotada no cálculo para livramento condicional: 1/3 - Comum primário
Extinto:Não Suspensão da pena: Não
EVENTOS DE INÍCIO, REINÍCIO E INTERRRUPÇÃO(ÕES) DO CUMPRIMENTO DA PENA
Tipo:PRISÃO/INÍCIO DE CUMPRIMENTO
Motivo:PRISÃO EM FLAGRANTE
Data:01/03/2024
Processos Selecionados:0000002-22.2019.8.12.0001
INCIDENTES CONCEDIDOS
Tipo:FIXAÇÃO/ALTERAÇÃO DE REGIME
Complemento:Fechado - Fixação inicial
Data Decisão: 05/03/2024 Data Referência:01/03/2024
Processos Selecionados:
INCIDENTES PENDENTES
Tipo:PROGRESSÃO DE REGIME
Complemento:Semiaberto
Data Decisão: Data Referência:
Processos Selecionados:
Fim do Relatório"""
ROD = "Processo Eletrônico - SEEU Gerado em: 13/10/2026 10:00:00 Pág.: %d de 2"


def paginas(cab=CAB, rod=ROD, p1=PAG1, p2=PAG2, topo=("", ""), pe=("", "")):
    out = []
    for n, corpo in ((1, p1), (2, p2)):
        linhas = [x for x in (topo[n - 1],) if x] + list(cab) + [corpo] + ([rod % n] if rod else []) + [x for x in (pe[n - 1],) if x]
        out.append("\n".join(linhas))
    return out


IGNORAR = ("arquivo", "_leitura_parcial", "_leitura_obs")


def juridico(r):
    return {k: v for k, v in r.items() if k not in IGNORAR}


base = rs.extrair_paginas(paginas(), "sintetico.pdf")
ok(base["processo_execucao"] == "0000001-11.2020.8.12.0001", "base: número da execução: %r" % base["processo_execucao"])
ok(base["tribunal"] == "TJMS" and base["comarca"] == "CIDADE FICTÍCIA" and base["vara"].startswith("1ª VARA DE EXECUÇÃO"),
   "base: cabeçalho %r %r %r" % (base["tribunal"], base["comarca"], base["vara"]))
ok(base["data_geracao_rspe"] == "13/10/2026", "base: data de geração")
ok(len(base["_crimes"]) == 1 and len(base["_eventos"]) == 1 and len(base["_incidentes"]) == 2,
   "base: 1 crime, 1 evento, 2 incidentes: %d %d %d" % (len(base["_crimes"]), len(base["_eventos"]), len(base["_incidentes"])))
ok(base["pena_total"] == "6a0m0d" and base["progressao_previsao_seeu"] == "01/11/2026" and base["termino_previsao_seeu"] == "01/03/2030",
   "base: cálculos da pena")
ok(not base.get("_leitura_parcial") and not base.get("_leitura_obs"), "base: leitura completa, sem observação: %s %s" % (
    base.get("_leitura_parcial"), base.get("_leitura_obs")))
REF = juridico(base)


def igual(nome, pags, obs_esperada=None):
    try:
        r = rs.extrair_paginas(pags, "sintetico.pdf")
    except Exception as e:
        ok(False, "%s: recusado (%s)" % (nome, e))
        return None
    j = juridico(r)
    difs = [k for k in set(j) | set(REF) if j.get(k) != REF.get(k)]
    ok(not difs, "%s: resultado jurídico diferente do RSPE original em %s" % (nome, difs))
    ok(not r.get("_leitura_parcial"), "%s: não é leitura parcial: %s" % (nome, r.get("_leitura_parcial")))
    if obs_esperada:
        ok(any(obs_esperada in o for o in r.get("_leitura_obs") or []), "%s: observação %r em %s" % (nome, obs_esperada, r.get("_leitura_obs")))
    return r


# 1) sem o título do relatório (tela "processoExecucaoPenal.do" salva em PDF)
igual("sem título", paginas(cab=CAB[:3]), "sem o título do relatório")
# execução arquivada sem o título: só cabeçalho, número e rodapé do SEEU - ainda é RSPE
_arq = rs.extrair_paginas(["\n".join(CAB[:3]) + "\nPROCESSO DE EXECUÇÃO\nNúmero Único: 0000003-33.2018.8.12.0001 (ARQUIVADO)\n"
                           "Nome: FULANO DE TAL\n" + ROD % 1], "x.pdf")
ok(_arq["processo_execucao"] == "0000003-33.2018.8.12.0001" and _arq["status_execucao"] == "ARQUIVADO",
   "execução arquivada sem título: lida (%r)" % _arq["processo_execucao"])
# 2) cabeçalho e rodapé do navegador ("Imprimir / Salvar como PDF") em cada página
nav_topo = ("13/10/2026, 14:22 SEEU - Processo Eletrônico de Execução Penal", "13/10/2026 14:22 processoExecucaoPenal.do")
nav_pe = ("https://seeu.pje.jus.br/seeu/processo/processoExecucaoPenal.do?x=1 1/2", "2/2")
igual("cabeçalho do navegador", paginas(cab=CAB[:3], topo=nav_topo, pe=nav_pe), "impressão pelo navegador")
igual("navegador em duas linhas", [("13/10/26 14:22\nprocessoExecucaoPenal.do\n" + p + "\nfile:///C:/Users/x/processoExecucaoPenal.do.html\n%d/2" % (i + 1))
                                   for i, p in enumerate(paginas())], "impressão pelo navegador")
igual("Página 1 de 2 do navegador", [p + "\nPágina %d de 2" % (i + 1) for i, p in enumerate(paginas())])
# 3) título em outra linha (antes do "PODER JUDICIÁRIO" ou depois da vara, já presente) e linha vazia no topo
igual("título antes do PODER JUDICIÁRIO", paginas(cab=[TIT] + CAB[:3]))
igual("linha vazia e título entre o PODER JUDICIÁRIO e o tribunal", paginas(cab=["", CAB[0], TIT, CAB[1], CAB[2]]))
# 4) tribunal e comarca na mesma linha do "PODER JUDICIÁRIO"
r = rs.extrair_paginas(paginas(cab=["PODER JUDICIÁRIO - TJMS - COMARCA DE CIDADE FICTÍCIA", CAB[2], TIT]), "x.pdf")
ok((r["tribunal"], r["comarca"], r["vara"]) == (base["tribunal"], base["comarca"], base["vara"]),
   "tribunal na linha do PODER JUDICIÁRIO: %r %r %r" % (r["tribunal"], r["comarca"], r["vara"]))
ok(len(r["_crimes"]) == 1 and r["pena_total"] == "6a0m0d", "tribunal na linha do PODER JUDICIÁRIO: crimes e cálculos lidos")
# 5) rodapé diferente (sem acento, sem dois-pontos, "Página")
igual("rodapé diferente", paginas(rod="Processo Eletronico  -  SEEU  Gerado em 13/10/2026 10:00:00  Página: %d de 2"))
# 6) texto inteiro sem acentos (outro leitor de PDF / impressão): RSPE reconhecido e lido
import unicodedata  # noqa: E402
sem_ac = ["".join(ch for ch in unicodedata.normalize("NFD", p) if unicodedata.category(ch) != "Mn") for p in paginas()]  # sem acento
ok(rs.e_rspe_seeu("\n".join(sem_ac)), "sem acentos: reconhecido como RSPE")
r = rs.extrair_paginas(sem_ac, "x.pdf")
ok(r["processo_execucao"] == base["processo_execucao"], "sem acentos: número da execução: %r" % r["processo_execucao"])
ok(r["pena_total"].upper() == "6A0M0D" and r["regime_atual"].upper().startswith("FECHADO"), "sem acentos: cálculos da pena: %r %r" % (
    r["pena_total"], r["regime_atual"]))
ok(r["termino_previsao_seeu"] == "01/03/2030" and r["progressao_previsao_seeu"] == "01/11/2026" and r["data_base_seeu"] == "01/03/2024",
   "sem acentos: previsões e data-base: %r %r %r" % (r["termino_previsao_seeu"], r["progressao_previsao_seeu"], r["data_base_seeu"]))
ok(len(r["_crimes"]) == 1 and len(r["_eventos"]) == 1 and len(r["_incidentes"]) == 2,
   "sem acentos: crimes, eventos e incidentes: %d %d %d" % (len(r["_crimes"]), len(r["_eventos"]), len(r["_incidentes"])))
ok(r["tribunal"] == "TJMS" and r["data_geracao_rspe"] == "13/10/2026", "sem acentos: tribunal e geração")
# minúsculas e espaços a mais nas marcas
ok(rs.e_rspe_seeu("Processo  de  Execucao\nNumero Unico : 0000001-11.2020.8.12.0001\nCalculos da pena\nprocesso eletronico - seeu Pag.: 1"),
   "marcas em minúsculas, sem acento e com espaços a mais")

# 7) seção corrompida (exceção no meio da leitura): leitura parcial com a seção afetada, o resto lido
orig_bt, orig_pc, orig_der = rs.blocos_tipo, rs.parse_crimes, rs.derivar


def bt_quebra(trecho):
    if "PRISÃO EM FLAGRANTE" in trecho:
        raise IndexError("list index out of range")
    return orig_bt(trecho)


rs.blocos_tipo = bt_quebra
try:
    r = rs.extrair_paginas(paginas(), "x.pdf")
    p = r.get("_leitura_parcial") or []
    ok(any("EVENTOS DE INÍCIO" in x and "IndexError" in x for x in p), "eventos com exceção: parcial com a seção: %s" % p)
    ok(not r["_eventos"] and len(r["_crimes"]) == 1 and len(r["_incidentes"]) == 2 and r["processo_execucao"],
       "eventos com exceção: o resto é lido")
finally:
    rs.blocos_tipo = orig_bt


def pc_quebra(trecho, sem_crime=None):
    raise KeyError("artigo")


rs.parse_crimes = pc_quebra
try:
    r = rs.extrair_paginas(paginas(), "x.pdf")
    ok(any("PROCESSOS CRIMINAIS" in x and "KeyError" in x for x in r.get("_leitura_parcial") or []),
       "crimes com exceção: parcial: %s" % r.get("_leitura_parcial"))
    ok(not r["_crimes"] and len(r["_eventos"]) == 1 and r["pena_total"] == "6a0m0d", "crimes com exceção: eventos e cálculos lidos")
finally:
    rs.parse_crimes = orig_pc


def der_quebra(r, crimes, eventos, incidentes):
    if incidentes:
        raise ZeroDivisionError("division by zero")
    return orig_der(r, crimes, eventos, incidentes)


rs.derivar = der_quebra
try:
    r = rs.extrair_paginas(paginas(), "x.pdf")
    p = r.get("_leitura_parcial") or []
    ok(any("incidentes" in x and "ZeroDivisionError" in x for x in p), "análise com exceção: incidentes de fora, parcial: %s" % p)
    ok(len(r["_crimes"]) == 1 and len(r["_eventos"]) == 1 and not r["_incidentes"], "análise com exceção: crimes e eventos mantidos")
finally:
    rs.derivar = orig_der


def calc_quebra(calc, rotulos):
    raise AttributeError("'NoneType' object has no attribute 'group'")


orig_prev = rs._previsao_seeu
rs._previsao_seeu = calc_quebra
try:
    r = rs.extrair_paginas(paginas(), "x.pdf")
    ok(any("previsão de progressão" in x for x in r.get("_leitura_parcial") or []) and r["pena_total"] == "6a0m0d" and len(r["_crimes"]) == 1,
       "cálculos com exceção: parcial e o resto lido: %s" % r.get("_leitura_parcial"))
finally:
    rs._previsao_seeu = orig_prev

# registro da importação: a leitura parcial aparece com a seção afetada
try:
    import rspe_app as app
    rs.blocos_tipo = bt_quebra
    try:
        r = rs.extrair_paginas(paginas(), "x.pdf")
    finally:
        rs.blocos_tipo = orig_bt
    obs, parcial = app._leitura_rspe(r, rs.campos_faltantes(r))
    ok(parcial and any("EVENTOS DE INÍCIO" in o for o in obs), "registro da importação: PARCIAL com a seção: %s" % obs)
    r = rs.extrair_paginas(paginas(cab=CAB[:3]), "x.pdf")
    obs, parcial = app._leitura_rspe(r, rs.campos_faltantes(r))
    ok(not parcial and any("sem o título" in o for o in obs), "registro: sem título é observação, não parcial: %s" % obs)
    ok("senha" in app._msg_erro_pdf(Exception("PDFPasswordIncorrect")), "mensagem de PDF protegido por senha")
except ImportError:
    pass

# 8) não é RSPE: recusado com o motivo
def recusa(nome, pags, trecho):
    try:
        rs.extrair_paginas(pags, "x.pdf")
        ok(False, "%s: deveria ser recusado" % nome)
    except ValueError as e:
        ok(trecho in str(e), "%s: motivo %r em %r" % (nome, trecho, str(e)))


recusa("atestado de pena", ["PODER JUDICIÁRIO\nTJMS - COMARCA DE CIDADE FICTÍCIA\nATESTADO DE PENA A CUMPRIR\nPROCESSO DE EXECUÇÃO\n"
                            "Número Único: 0000001-11.2020.8.12.0001\nPena Total Imposta: 6a0m0d\nCÁLCULOS DA PENA\n" + ROD % 1],
       "atestado de pena")
recusa("petição", ["EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA VARA DE EXECUÇÃO PENAL\nProcesso de execução nº 0000001-11.2020.8.12.0001\n"
                   "FULANO DE TAL, já qualificado, vem requerer a progressão de regime."], "petição")
recusa("outro documento", ["Contrato de locação\nCláusula primeira"], "faltam as marcas do relatório")
recusa("PDF digitalizado (sem texto)", ["", "  "], "sem texto")
ok(not rs.e_rspe_seeu("PODER JUDICIÁRIO\nPROCESSO DE EXECUÇÃO\nNúmero Único: 0000000-00.2020.8.12.0001\nAtestado de pena"),
   "só cabeçalho e número não bastam")

# 9) ficha disciplinar: variações e falhas
FICHA_P1 = """AGÊNCIA ESTADUAL DE ADMINISTRAÇÃO DO SISTEMA PENITENCIÁRIO - AGEPEN
SISTEMA INTEGRADO DE ADMINISTRAÇÃO PENITENCIÁRIA - SIAPEN
FICHA DISCIPLINAR (ID: 1 )
Nome: FULANO DE TAL RGI: 12345
CPF: 000.000.000-00
Filiação: MARIA DE TAL \\ JOSÉ DE TAL
Data Nascimento:01/01/1990
Data Prisão: 01/03/2024 Procedência: DP Condenação: CONDENADO
Data Entrada: 02/03/2024 Unidade Penal: ESTABELECIMENTO PENAL FICTÍCIO
HISTÓRICO - CONDUTA: BOA
02.03.2024 - Entrada na Unidade Penal: ESTABELECIMENTO PENAL FICTÍCIO, Procedente: DP, Conforme OF 1/2024.
10.04.2024 - TRABALHO: Iniciou atividade laboral, no setor de trabalho COZINHA, conforme documento CI 1/2024.
Impresso em 13/10/2026"""
ok(rf.e_ficha(FICHA_P1) and rf.e_ficha(rs._sem_acento(FICHA_P1).lower()), "ficha reconhecida com e sem acento, em minúsculas")
ok(not rs.e_rspe_seeu(FICHA_P1), "ficha não é RSPE")
f0 = rf._extrair_texto("ficha.pdf", [FICHA_P1], [FICHA_P1])
ok(f0["nome"] == "FULANO DE TAL" and len(f0["eventos"]) == 2 and not f0.get("_leitura_parcial"), "ficha base: %s %s" % (
    f0["nome"], f0.get("_leitura_parcial")))
f1 = rf._extrair_texto("ficha.pdf", [FICHA_P1], [rs.sem_linhas_navegador("13/10/2026 14:22 SIAPEN\n" + FICHA_P1 + "\nhttps://siapen.ms.gov.br/ficha 1/1")[0]])
ok(f1["nome"] == f0["nome"] and f1["eventos"] == f0["eventos"], "ficha com cabeçalho do navegador: mesma leitura")
f2 = rf._extrair_texto("ficha.pdf", [FICHA_P1], [FICHA_P1.replace("HISTÓRICO", "HISTORICO")])
ok(f2["nome"] == f0["nome"] and f2["eventos"] == f0["eventos"] and f2["conduta"] == f0["conduta"], "ficha com HISTORICO sem acento")
orig_fd = rf.derivar


def fd_quebra(f, eventos):
    if eventos:
        raise ValueError("data inválida")
    return orig_fd(f, eventos)


rf.derivar = fd_quebra
try:
    f3 = rf._extrair_texto("ficha.pdf", [FICHA_P1], [FICHA_P1])
    obs, parcial = rf.leitura_parcial(f3)
    ok(parcial and any("análise do histórico" in o for o in obs), "ficha com exceção na análise: parcial: %s" % obs)
    ok(f3["nome"] == "FULANO DE TAL" and len(f3["eventos"]) == 2, "ficha com exceção: cabeçalho e lançamentos guardados")
finally:
    rf.derivar = orig_fd

# 10) PDF de verdade (reportlab, se instalado): sem título + navegador; sem texto; protegido por senha
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:
    canvas = None
if canvas is not None:
    tmp = tempfile.mkdtemp(prefix="rspe_robusta_")

    def pdf(nome, pags, enc=None):
        c = canvas.Canvas(os.path.join(tmp, nome), pagesize=A4, encrypt=enc)
        for p in pags:
            y = 820
            for l in p.split("\n"):
                c.setFont("Helvetica", 7)
                c.drawString(20, y, l)
                y -= 9
            c.showPage()
        c.save()
        return os.path.join(tmp, nome)
    try:
        caminho = pdf("processoExecucaoPenal.do.pdf", paginas(cab=CAB[:3], topo=nav_topo, pe=nav_pe))
        r = rs.extrair(caminho)
        ok(r["processo_execucao"] == base["processo_execucao"] and len(r["_crimes"]) == 1 and len(r["_eventos"]) == 1
           and r["vara"] == base["vara"] and not r.get("_leitura_parcial"), "PDF sem título e com navegador: lido por inteiro")
        try:
            rs.extrair(pdf("branco.pdf", [""]))
            ok(False, "PDF sem texto deveria ser recusado")
        except ValueError as e:
            ok("sem texto" in str(e), "PDF sem texto: motivo: %s" % e)
        try:
            from reportlab.lib import pdfencrypt
            enc = pdfencrypt.StandardEncryption("senha123", ownerPassword="dono", canPrint=1, strength=128)
            caminho = pdf("protegido.pdf", paginas(), enc)
            try:
                rs.extrair(caminho)
                ok(False, "PDF com senha deveria ser recusado")
            except ValueError as e:
                ok("senha" in str(e), "PDF protegido: motivo: %s" % e)
        except ImportError:
            pass
    finally:
        for f_ in os.listdir(tmp):
            os.remove(os.path.join(tmp, f_))
        os.rmdir(tmp)

# PDF de impressora virtual (PDFCreator): texto só em "(cid:N)" - recusado com o motivo certo
try:
    rs.ler_paginas(["".join("(cid:%d)" % (i % 90) for i in range(400))])
    ok(False, "PDF de impressora virtual deveria ser recusado")
except ValueError as e:
    ok("impressora virtual" in str(e), "motivo da recusa do PDF de impressora virtual: %s" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f_ in falhas:
        print(" -", f_)
    sys.exit(1)
print("teste_leitura_robusta: ok")
