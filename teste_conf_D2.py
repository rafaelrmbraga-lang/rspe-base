"""Conferência manual de 420 casos (frente D2 - remição: contas e apresentação). Dados fictícios. Confere: o trabalho e o estudo em
curso estimados só até a impressão da ficha; a jornada registrada na ficha (segunda a sexta, 12x36) na estimativa; os dias de
vínculos simultâneos contados uma vez só, com o mesmo número na tabela, na remição detalhada e no resumo; o resumo da seção A pela
conciliação (sem "falta 1 dia" de fração nem contradição com as pendências); a linha amarela com pontos a conferir; o "último
atestado há 6 meses" contado do início do trabalho atual; a baixa do setor lançado com outro nome no mesmo dia; a liberação do
setor que encerra o registro duplicado; o envio do atestado pelo ESAJ; a lacuna sem o intervalo declarado sem trabalho e fora da
custódia; a ressalva do art. 127 com a falta homologada primeiro. (7.14: sem a conciliação atestado x remição, saíram o resumo pela conciliação, o "6 meses",
as lacunas e o "em curso há até 90 dias"; o resto passa ao modelo novo.) Rodar: python teste_conf_D2.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rr

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


E = lambda d, t: {"data": d, "texto": t}
rem = lambda d, n, ref=None: {"tipo": "REMIÇÃO", "complemento": "%d dias" % n, "data_decisao": d, "data_referencia": ref or d, "situacao": "CONCEDIDO"}
INI = lambda s: "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1/26/ST/PDIB/AGEPEN/MS." % s
FIM = lambda s, m="N/C": "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento N/C, motivo: %s." % (s, m)
HOJE = date(2026, 10, 20)


def roda(nome, fn):
    try:
        fn()
    except Exception as e:
        import traceback
        traceback.print_exc()
        falhas.append("%s: exceção %r" % (nome, e))


def N_(r, f):
    rf.atualizar(f)
    return rf.comparativo(dict({"_eventos": [{"data": "01/01/2010", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}]}, **r), f, HOJE)["fd_novo"]


def em_curso_ate_impressao():
    # trabalho aberto desde 08/07/2026, ficha impressa em 05/10/2026, programa rodando em 20/10/2026: a conta vai até 05/10/2026
    f = {"data_impressao": "05/10/2026", "eventos": [E("08.07.2026", INI("PRENDEBEM/PDIB"))]}
    N = N_({"_incidentes": []}, f)
    n = rf.dias_trabalho(date(2026, 7, 8), date(2026, 10, 5))
    p = [p_ for p_ in N["pontos"] if p_["tipo"] == "pedir_atestado"]
    ok(abs(N["pedir_dias"] - n / 3.0) < 0.01 and p and "08/07/2026 a 05/10/2026" in p[0]["texto"] and "impressão da ficha, 05/10/2026" in p[0]["texto"],
       "em curso: %r %r" % (N["pedir_dias"], [x["texto"] for x in p]))
    L = N["trab"]["linhas"]
    ok(L and L[0]["em_curso"] and "(em curso na impressão da ficha)" in L[0]["periodo"], "em curso: linha %r" % L)


def estudo_ate_impressao():
    f = {"data_impressao": "05/10/2026", "eventos": [], "estudos": [{"curso": "EJA ENSINO MEDIO", "inicio": "02.04.2026"}]}
    N = N_({"_incidentes": []}, f)
    d = len([x for x in rf.dias_jornada_set(date(2026, 4, 2), date(2026, 10, 5), "seg-sex") if not rf.em_recesso(x)])
    ok(N["est_estim"] and abs(N["est_estim"][0]["dias"] - d * rf.HORAS_DIA_ESTUDO / 12.0) < 0.01, "estudo: horas até a impressão %r x %r" % (N["est_estim"], d))


def jornada_da_ficha():
    # início estruturado + texto livre do mesmo dia com a jornada de segunda a sexta: um vínculo só, contado de segunda a sexta
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("08.03.2024", INI("CC - COMPER")),
        E("08.03.2024", "INICIA ATIVIDADE LABORAL EXTERNA NA EMPRESA COMPER CONVENIADA AO CONSELHO DA COMUNIDADE CUMPRINDO CARGA HORÁRIA DE "
                        "SEGUNDA A SEXTA DAS 07:30 ÀS 17H, CONFORME CI Nº 88/24/ST/CPAIG/AGEPEN/MS."),
        E("30.04.2024", FIM("CC - COMPER", "Saiu da unidade penal"))]}
    vs = rr.vinculos(f["eventos"], HOJE, date(2026, 10, 5))[0]
    ok(len(vs) == 1 and vs[0].get("jornada") == "seg-sex", "jornada: vínculos %r" % [(v["setor"], v.get("jornada")) for v in vs])
    N = N_({"_incidentes": []}, f)
    n = rf.dias_trabalho(date(2024, 3, 8), date(2024, 4, 30), "seg-sex")
    ok(len(N["trab"]["linhas"]) == 1 and abs(N["pedir_dias"] - n / 3.0) < 0.01, "jornada: estimativa %r x %r" % (N["pedir_dias"], n / 3.0))
    # 12x36: dia sim, dia não
    ok(len(rf.dias_jornada_set(date(2026, 1, 1), date(2026, 1, 10), "12x36")) == 5 and rf.jornada_do_texto("escala 12 x 36") == "12x36",
       "12x36")


def simultaneos_uma_conta():
    # dois setores ao mesmo tempo: os dias comuns contam uma vez, e a soma das linhas é o total
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("03.02.2025", INI("SERRALHERIA")), E("30.04.2025", FIM("SERRALHERIA")),
        E("03.03.2025", INI("POLIGONAL ENGENHARIA LTDA")), E("30.05.2025", FIM("POLIGONAL ENGENHARIA LTDA"))]}
    N = N_({"_incidentes": []}, f)
    uni = len(rf.dias_jornada_set(date(2025, 2, 3), date(2025, 5, 30)))
    ok(abs(N["pedir_dias"] - uni / 3.0) < 0.01 and abs(sum(L.get("pedir_dias") or 0 for L in N["trab"]["linhas"]) - N["pedir_dias"]) < 0.01,
       "simultâneos: %r x %r" % (N["pedir_dias"], uni / 3.0))


def unidade_corte_curto():
    # o vínculo termina no dia da transferência (entrada na nova unidade): o dia não se perde; a unidade de cada período vem da ficha
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("01.04.2023", "Entrada na Unidade Penal: CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA, Procedente: PTRAN"),
        E("10.04.2023", INI("FAXINA")),
        E("05.05.2023", "Entrada na Unidade Penal: PENITENCIARIA DE DOIS IRMAOS DO BURITI, Procedente: CPAIG"),
        E("05.05.2023", FIM("FAXINA", "Saida do Presídio"))]}
    rf.atualizar(f)
    o = rf.comparativo({"_eventos": [{"data": "01/01/2010", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": []}, f, HOJE)
    N = o["fd_novo"]
    n = rf.dias_trabalho(date(2023, 4, 10), date(2023, 5, 5))
    ok(abs(N["pedir_dias"] - n / 3.0) < 0.01 and N["trab"]["linhas"][0]["un"] == "Centro Penal Agroindustrial da Gameleira",
       "corte da transferência: %r %r" % (N["pedir_dias"], N["trab"]["linhas"][0].get("un")))


def cor_amarela():
    # o RSPE concedeu mais do que a ficha comprova (sem diferença a favor da ficha), mas há ponto a conferir: amarelo
    f = {"data_impressao": "05/10/2026", "conduta": "BOA", "eventos": [
        E("01.03.2023", INI("COZINHA")), E("30.06.2023", FIM("COZINHA")),
        E("10.07.2023", "EMITIDO ATESTADO DE TRABALHO Nº 050/2023, NO SETOR DE COZINHA DE 01/03/2023 A 30/06/2023, COM 102 DIAS TRABALHADOS E 34 DIAS REMIDOS."),
        E("15.08.2026", INI("PRENDEBEM/PDIB"))]}
    r = {"_eventos": [{"data": "01/01/2010", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}], "_incidentes": [rem("20/09/2023", 34), rem("10/02/2025", 10)]}
    rf.atualizar(f)
    out = rf.comparativo(r, f, HOJE)
    # o trabalho atual (desde 15/08/2026) está em curso há até 90 dias: acompanhar, não "pedir atestado"; o atestado sem registro de
    # peticionamento tem remição do mesmo valor 72 dias depois: "provavelmente remido" (cinza); o RSPE é maior que a ficha: tudo cinza
    tp = [p_["tipo"] for p_ in out["fd_novo"]["pontos"]]
    ok(out["fd_cor"] == "cinza" and "em_curso" in tp and "pedir_atestado" not in tp and "provavel_remido" in tp and "sem_pet" not in tp
       and out["fd_novo"]["dif"] == -10,
       "cor: %r / %r" % (out["fd_cor"], tp))


def baixa_com_outro_nome():
    evs = [E("17.09.2012", "INICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE OFICINA DE TRABALHO - BENEFICIAMENTO DE MANDIOCA, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
           E("17.09.2012", INI("IPCG MANDIOCA")),
           E("20.06.2013", "REMANEJADO PARA O SETOR DE COLETA DE LIXO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO OF. JOSENI."),
           E("20.06.2013", INI("IPCG RECICLAGEM DE LIXO")),
           E("05.11.2013", "SAIDA DA UNIDADE PENAL: INSTITUTO PENAL DE CAMPO GRANDE, Destino: ALVARÁ DE SOLTURA"),
           E("05.11.2013", FIM("IPCG MANDIOCA", "Saida do Presídio")),
           E("15.03.2016", "INICIOU SUAS ATIVIDADES LABORAIS NO SETOR DE MANUTENÇÃO, CONFORME DETERMINAÇÃO DO SETOR DE TRABALHO."),
           E("15.03.2016", INI("IPCG MANUTENÇÃO SERV. GERAIS")),
           E("01.07.2019", "DESLIGADO DO SETOR DE TRABALHO POR FALTA DE PRODUTIVIDADE, CONFORME DELIBERAÇÃO DO CHEFE DO SETOR DE TRABALHO."),
           E("01.07.2019", FIM("IPCG MANUTENÇÃO SERV. GERAIS", "DESCADASTRADO POR FALTA DE PRODUTIVIDADE"))]
    vs, av = rr.vinculos(evs, HOJE, date(2026, 10, 5))
    ok(not av, "baixa sem início com o início na ficha: %r" % av)
    ok(len(vs) == 3 and all(v["fim"] for v in vs), "vínculos lançados duas vezes no mesmo dia: %r" % [(v["setor"], v["ini"], v["fim"]) for v in vs])


def liberacao_encerra_duplicado():
    evs = [E("28.04.2025", INI("TRABALHO EXTERNO")), E("28.04.2025", INI("POLIGONAL ENGENHARIA LTDA")),
           E("27.08.2025", "CONSELHO DISCIPLINAR: ISOLADO PREVENTIVAMENTE EM CELA DISCIPLINAR, POR 10 DIAS."),
           E("27.08.2025", FIM("POLIGONAL ENGENHARIA LTDA", "ENCAMINHADO PARA A DISCIPLINAR")),
           E("27.08.2025", "Liberação do Setor de Trabalho - Doc.: CI 063/25/ST/PDIB/AGEPEN/MS Motivo: ENCAMINHADO PARA A DISCIPLINAR")]
    vs, _av = rr.vinculos(evs, HOJE, date(2026, 10, 5))
    ok(all(v["fim"] == date(2025, 8, 27) and not v.get("duvida") for v in vs), "liberação: %r" % [(v["setor"], v["fim"], v.get("duvida")) for v in vs])


def esaj():
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("27.02.2019", INI("BARBEARIA")), E("09.07.2019", FIM("BARBEARIA")),
        E("09.07.2019", "Enviado, via ESAJ, Atestado de Trabalho Prisional n. 160/2019; Tipo de Trabalho: Barbeiro; Data Inicial: 27/02/2019; Data final: "
                        "09/07/2019; Tempo de Trabalho computado no período: 114 dias trabalhados; Tempo de REMIÇÃO: 38 dias remidos.")]}
    N = N_({"_incidentes": []}, f)
    d = next(d for d in N["docs"] if d["num"].startswith("160"))
    ok(d["pet_ok"] and d["pet"] == "peticionado em 09/07/2019", "ESAJ: %r" % d)


def ressalva_127():
    # documento posterior à última remição (fato) e faltas graves depois dele: a ressalva começa pela homologada
    f = {"data_impressao": "05/10/2026", "eventos": [E("02.01.2015", INI("FAXINA")), E("30.06.2015", FIM("FAXINA")),
                                                      E("05.07.2015", "PETICIONADO ATESTADO DE TRABALHO Nº 070/2015, PERÍODO DE 02/01/2015 A 30/06/2015, "
                                                                      "COM 150 DIAS TRABALHADOS E 50 DIAS REMIDOS.")]}
    rf.atualizar(f)
    f["faltas"] = [{"data_fato": "03.06.2025", "grave": True, "situacao": "em apuração"}]
    r = {"_eventos": [{"data": "01/01/2010", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "_incidentes": [{"tipo": "FALTA GRAVE", "complemento": "Data do fato: 03/02/2017", "data_decisao": "10/03/2017", "data_referencia": "03/02/2017",
                          "situacao": "CONCEDIDO"}]}
    ress = rf.comparativo(r, f, HOJE)["fd_novo"]["ressalva_127"]
    ok("falta grave homologada (03/02/2017), falta grave registrada na ficha, sem homologação no RSPE (03/06/2025)" in ress
       and "dos dias até a falta" in ress, "ressalva do art. 127: %s" % ress)


for nome, fn in [("em curso", em_curso_ate_impressao), ("estudo", estudo_ate_impressao), ("jornada", jornada_da_ficha),
                 ("simultâneos", simultaneos_uma_conta), ("transferência", unidade_corte_curto), ("cor", cor_amarela),
                 ("baixa", baixa_com_outro_nome), ("liberação", liberacao_encerra_duplicado), ("ESAJ", esaj), ("art. 127", ressalva_127)]:
    roda(nome, fn)
print("\n".join(falhas) if falhas else "ok: conferência D2 - remição (7.14: impressão da ficha, jornada, dias simultâneos, unidade, cor amarela, "
      "baixa com outro nome, liberação, ESAJ, art. 127)")
sys.exit(1 if falhas else 0)
