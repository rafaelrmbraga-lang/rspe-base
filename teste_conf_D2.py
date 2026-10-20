"""Conferência manual de 420 casos (frente D2 - remição: contas e apresentação). Dados fictícios. Confere: o trabalho e o estudo em
curso estimados só até a impressão da ficha; a jornada registrada na ficha (segunda a sexta, 12x36) na estimativa; os dias de
vínculos simultâneos contados uma vez só, com o mesmo número na tabela, na remição detalhada e no resumo; o resumo da seção A pela
conciliação (sem "falta 1 dia" de fração nem contradição com as pendências); a linha amarela com pontos a conferir; o "último
atestado há 6 meses" contado do início do trabalho atual; a baixa do setor lançado com outro nome no mesmo dia; a liberação do
setor que encerra o registro duplicado; o envio do atestado pelo ESAJ; a lacuna sem o intervalo declarado sem trabalho e fora da
custódia; a ressalva do art. 127 com a falta homologada primeiro. Rodar: python teste_conf_D2.py"""
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


def em_curso_ate_impressao():
    # trabalho aberto desde 08/07/2026, ficha impressa em 05/10/2026, programa rodando em 20/10/2026: a conta vai até 05/10/2026
    f = {"data_impressao": "05/10/2026", "eventos": [E("08.07.2026", INI("PRENDEBEM/PDIB"))]}
    linhas, res = rf.quadro_trabalho({"_incidentes": []}, f, HOJE)
    C = res["conc"]
    n = rf.dias_trabalho(date(2026, 7, 8), date(2026, 10, 5))
    p = [p_ for p_ in C["pendencias"] if p_["status"] == "SEM_ATESTADO"]
    ok(len(p) == 1 and "08/07/2026 a 05/10/2026 (em curso; até a impressão da ficha)" in p[0]["texto"]
       and "≈ %d dias, ≈ %d remidos" % (n, n // 3) in p[0]["texto"], "em curso: pendência %r" % [x["texto"] for x in p])
    D = res["rem_det"]
    ok(D["sem_atestado"]["dias"] == n // 3 and D["total"] == n // 3, "em curso: remição detalhada %r" % D["sem_atestado"])
    ok(res["sem_atestado_a_requerer"] == n // 3, "em curso: a requerer %r" % res["sem_atestado_a_requerer"])
    R = C["resumo"]["texto"]
    ok("05/10/2026 (data de impressão da ficha)" in R and "cerca de %d dias de remição" % (n // 3) in R and "hoje" not in R, "em curso: resumo %s" % R)
    ok(any("desde 08/07/2026, em curso" in x for x in res["sem_atestado_f"]), "em curso: fundamentação %r" % res["sem_atestado_f"])
    # há até 90 dias (contados até hoje): ainda em curso, fora do total
    f2 = {"data_impressao": "05/10/2026", "eventos": [E("01.08.2026", INI("PRENDEBEM/PDIB"))]}
    _l, res2 = rf.quadro_trabalho({"_incidentes": []}, f2, HOJE)
    p2 = [p_ for p_ in res2["conc"]["pendencias"] if p_["status"] == "EM_CURSO"]
    n2 = rf.dias_trabalho(date(2026, 8, 1), date(2026, 10, 5))
    ok(len(p2) == 1 and "≈ %d dias, ≈ %d remidos" % (n2, n2 // 3) in p2[0]["texto"] and res2["rem_det"]["total"] == 0
       and res2["rem_det"]["em_curso"]["dias"] == n2 // 3, "em curso há até 90 dias: %r / %r" % ([x["texto"] for x in p2], res2["rem_det"]["em_curso"]))


def estudo_ate_impressao():
    f = {"data_impressao": "05/10/2026", "eventos": [], "estudos": [{"curso": "EJA ENSINO MEDIO", "inicio": "02.04.2026"}]}
    _l, res = rf.quadro_trabalho({"_incidentes": []}, f, HOJE)
    h = rf._dias_uteis(date(2026, 4, 2), date(2026, 10, 5)) * rf.HORAS_DIA_ESTUDO
    ok(res["estudo_horas_pend"] == h and res["estudo_dias_pend"] == h // 12, "estudo: horas até a impressão %r x %r" % (res["estudo_horas_pend"], h))


def jornada_da_ficha():
    # início estruturado + texto livre do mesmo dia com a jornada de segunda a sexta: um vínculo só, contado de segunda a sexta
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("08.03.2024", INI("CC - COMPER")),
        E("08.03.2024", "INICIA ATIVIDADE LABORAL EXTERNA NA EMPRESA COMPER CONVENIADA AO CONSELHO DA COMUNIDADE CUMPRINDO CARGA HORÁRIA DE "
                        "SEGUNDA A SEXTA DAS 07:30 ÀS 17H, CONFORME CI Nº 88/24/ST/CPAIG/AGEPEN/MS."),
        E("30.04.2024", FIM("CC - COMPER", "Saiu da unidade penal"))]}
    C = rr.conciliar({"_incidentes": []}, f, HOJE)
    vs = C["vinculos"]
    ok(len(vs) == 1 and vs[0].get("jornada") == "seg-sex", "jornada: vínculos %r" % [(v["setor"], v.get("jornada")) for v in vs])
    n = rf.dias_trabalho(date(2024, 3, 8), date(2024, 4, 30), "seg-sex")
    p = [p_ for p_ in C["pendencias"] if p_["status"] == "SEM_ATESTADO"]
    ok(len(p) == 1 and "estimativa seg.-sex., jornada registrada na ficha: ≈ %d dias, ≈ %d remidos" % (n, n // 3) in p[0]["texto"],
       "jornada: pendência %r" % [x["texto"] for x in p])
    ok(not any(a["tipo"] == "vínculos sobrepostos" for a in C["alertas"]), "jornada: sobreposição falsa %r" % C["alertas"])
    # 12x36: dia sim, dia não
    ok(len(rf.dias_jornada_set(date(2026, 1, 1), date(2026, 1, 10), "12x36")) == 5 and rf.jornada_do_texto("escala 12 x 36") == "12x36",
       "12x36")


def simultaneos_uma_conta():
    # dois setores ao mesmo tempo (sem baixa que prove o fim de um deles): os dias comuns contam uma vez; a tabela (pendências), a
    # remição detalhada e o resumo dão o mesmo número
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("03.02.2025", INI("SERRALHERIA")), E("30.04.2025", FIM("SERRALHERIA")),
        E("03.03.2025", INI("POLIGONAL ENGENHARIA LTDA")), E("30.05.2025", FIM("POLIGONAL ENGENHARIA LTDA"))]}
    _l, res = rf.quadro_trabalho({"_incidentes": []}, f, HOJE)
    C, D = res["conc"], res["rem_det"]
    uni = len(rf.dias_jornada_set(date(2025, 2, 3), date(2025, 5, 30)))
    tot_p = sum(x["rem"] for x in C["sem_atestado"])
    ok(D["sem_atestado"]["dias"] == tot_p == sum(i["dias"] for i in D["sem_atestado"]["itens"]), "simultâneos: detalhada x pendências %r / %r" % (
        D["sem_atestado"], tot_p))
    ok(abs(tot_p - uni // 3) <= 1, "simultâneos: dias contados duas vezes (%r x %r)" % (tot_p, uni // 3))
    pol = next(p_ for p_ in C["pendencias"] if p_["texto"].startswith("Poligonal"))
    ok("simultâneos a outro vínculo (já contados)" in pol["texto"], "simultâneos: aviso na pendência %r" % pol["texto"])
    ok("cerca de %d dias de remição" % tot_p in C["resumo"]["texto"], "simultâneos: resumo %s" % C["resumo"]["texto"])


def unidade_corte_curto():
    # o vínculo termina no dia da transferência (entrada na nova unidade): o dia não se perde na remição detalhada
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("01.04.2023", "Entrada na Unidade Penal: CENTRO PENAL AGROINDUSTRIAL DA GAMELEIRA, Procedente: PTRAN"),
        E("10.04.2023", INI("FAXINA")),
        E("05.05.2023", "Entrada na Unidade Penal: PENITENCIARIA DE DOIS IRMAOS DO BURITI, Procedente: CPAIG"),
        E("05.05.2023", FIM("FAXINA", "Saida do Presídio"))]}
    _l, res = rf.quadro_trabalho({"_incidentes": []}, f, HOJE)
    n = rf.dias_trabalho(date(2023, 4, 10), date(2023, 5, 5))
    p = [p_ for p_ in res["conc"]["pendencias"] if p_["status"] == "SEM_ATESTADO"]
    ok(p and "≈ %d remidos" % (n // 3) in p[0]["texto"] and res["rem_det"]["sem_atestado"]["dias"] == n // 3,
       "corte da transferência: %r / %r" % ([x["texto"] for x in p], res["rem_det"]["sem_atestado"]))


def resumo_pela_conciliacao():
    # atestado com período (sem remição) + remição do RSPE sem origem: o resumo diz o que falta do atestado, não a diferença bruta
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("01.03.2024", INI("COZINHA")), E("30.06.2024", FIM("COZINHA")),
        E("10.07.2024", "EMITIDO ATESTADO DE TRABALHO Nº 112/2024, NO SETOR DE COZINHA DE 01/03/2024 A 30/06/2024, COM 69 DIAS TRABALHADOS E 23 DIAS REMIDOS.")]}
    r = {"_incidentes": [rem("20/12/2023", 3), rem("15/01/2024", 20)]}
    C = rr.conciliar(r, f, HOJE)
    R = C["resumo"]["texto"]
    ok("faltam cerca de 23 dias, do atestado sem remição correspondente no RSPE (nº 112/2024)" in R and "faltam cerca de 1 dia" not in R
       and "23 dias de remição sem origem identificada" in R, "resumo: %s" % R)
    ok(C["resumo"]["pend_atestados"] == 23, "resumo: campo %r" % C["resumo"])
    # atestados todos conciliados, com fração (60 + 89,33 + 92,33 = 241,66 x 241 no RSPE): correspondem, sem "falta 1 dia"
    f2 = {"data_impressao": "05/10/2026", "eventos": [
        E("10.01.2024", "EMITIDO ATESTADO DE TRABALHO Nº 001/2024, NO SETOR DE FAXINA DE 02/01/2023 A 31/12/2023, COM 268 DIAS TRABALHADOS E 89,33 DIAS REMIDOS.")]}
    C2 = rr.conciliar({"_incidentes": [rem("20/02/2024", 89)]}, f2, HOJE)
    R2 = C2["resumo"]["texto"]
    ok("correspondem aos atestados da ficha" in R2 and "faltam" not in R2, "resumo com fração: %s" % R2)


def cor_amarela_e_seis_meses():
    # sem nada a requerer, mas com remição do RSPE sem origem na ficha: amarelo, não "Em ordem"; o trabalho atual começou depois do
    # último atestado (de 2023) e há menos de 6 meses: sem o aviso de atestado vencido
    f = {"data_impressao": "05/10/2026", "conduta": "BOA", "eventos": [
        E("01.03.2023", INI("COZINHA")), E("30.06.2023", FIM("COZINHA")),
        E("10.07.2023", "EMITIDO ATESTADO DE TRABALHO Nº 050/2023, NO SETOR DE COZINHA DE 01/03/2023 A 30/06/2023, COM 102 DIAS TRABALHADOS E 34 DIAS REMIDOS."),
        E("15.08.2026", INI("PRENDEBEM/PDIB"))]}
    r = {"_incidentes": [rem("20/09/2023", 34), rem("10/02/2025", 10)]}
    out = rf.comparativo(r, f, HOJE)
    ok(out["fd_cor"] == "amarelo" and out["fd_sit"] != "Em ordem" and any("sem origem na ficha" in i["t"] for i in out.get("fd_sit_itens") or []),
       "cor: %r / %r" % (out["fd_cor"], out.get("fd_sit_itens")))
    ok(not any("6 meses" in i["t"] for i in out.get("fd_sit_itens") or []), "6 meses com trabalho novo: %r" % out.get("fd_sit_itens"))
    # trabalho atual desde 01/01/2026, sem atestado: há mais de 6 meses na impressão - o aviso fala do trabalho atual
    f2 = dict(f, eventos=f["eventos"][:3] + [E("01.01.2026", INI("PRENDEBEM/PDIB"))])
    out2 = rf.comparativo(r, f2, HOJE)
    ok(any(i["t"].startswith("Trabalho em curso desde 01/01/2026 sem atestado há mais de 6 meses") for i in out2.get("fd_sit_itens") or []),
       "6 meses desde o início do trabalho atual: %r" % out2.get("fd_sit_itens"))


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
    C = rr.conciliar({"_incidentes": []}, {"data_impressao": "05/10/2026", "eventos": evs}, HOJE)
    ok(not any(p_["status"] == "A_CONFERIR" and "2026" in p_["texto"] for p_ in C["pendencias"]), "liberação: trabalho a conferir depois dela %r" % C["pendencias"])


def esaj():
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("27.02.2019", INI("BARBEARIA")), E("09.07.2019", FIM("BARBEARIA")),
        E("09.07.2019", "Enviado, via ESAJ, Atestado de Trabalho Prisional n. 160/2019; Tipo de Trabalho: Barbeiro; Data Inicial: 27/02/2019; Data final: "
                        "09/07/2019; Tempo de Trabalho computado no período: 114 dias trabalhados; Tempo de REMIÇÃO: 38 dias remidos.")]}
    C = rr.conciliar({"_incidentes": []}, f, HOJE)
    a = next(a for a in C["atestados"] if a["numero"].startswith("160"))
    p = next(p_ for p_ in C["pendencias"] if p_["status"] == "NAO_LANCADO")
    ok(a["peticionado"] and a.get("esaj") and "ESAJ" in p["texto"] and "decisão no ESAJ" in p["acao"] and "pedir o peticionamento" not in p["acao"],
       "ESAJ: %r / %r" % (a.get("peticionado"), p))


def lacunas():
    # o atestado declara o intervalo sem trabalho: não é lacuna
    f = {"data_impressao": "05/10/2026", "eventos": [
        E("21.01.2014", INI("ARTESANATO")), E("10.06.2014", FIM("ARTESANATO")),
        E("10.06.2014", "FOI EMITIDO ATESTADO DE TRABALHO Nº 419/EPJFC/2014, NO SETOR DE ARTESANATO DE 21/01/2014 A 09/02/2014, NO SETOR DE ARTESANATO "
                        "DE 06/03/2014 A 10/06/2014. CALCULADOS 100 DIAS TRABALHADOS E 33 DIAS REMIDOS. DE 10/02/2014 A 05/03/2014 O INTERNO NÃO "
                        "EFETUOU QUALQUER ATIVIDADE LABORATIVA.")]}
    C = rr.conciliar({"_incidentes": [rem("10/08/2014", 33)]}, f, HOJE)
    ok(not any(p_["status"] == "LACUNA" for p_ in C["pendencias"]), "lacuna declarada sem trabalho: %r" % C["pendencias"])
    # entre dois atestados, a pessoa esteve solta (interrupção no RSPE): a lacuna é só o trecho preso
    f2 = {"data_impressao": "05/10/2026", "eventos": [
        E("10.01.2013", "EMITIDO ATESTADO DE TRABALHO Nº 010/2013, NO SETOR DE MANDIOCA DE 17/09/2012 A 04/11/2013, COM 300 DIAS TRABALHADOS E 100 DIAS REMIDOS."),
        E("20.06.2024", "EMITIDO ATESTADO DE TRABALHO Nº 065/2024, NO SETOR DE FAXINA DE 16/04/2024 A 15/06/2024, COM 51 DIAS TRABALHADOS E 17 DIAS REMIDOS.")]}
    r2 = {"_incidentes": [], "_eventos": [{"data": "05/11/2013", "tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA"},
                                          {"data": "05/10/2023", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}]}
    C2 = rr.conciliar(r2, f2, HOJE)
    lac = [p_["texto"] for p_ in C2["pendencias"] if p_["status"] == "LACUNA"]
    ok(len(lac) == 1 and lac[0].startswith("05/10/2023 a 15/04/2024"), "lacuna fora da custódia: %r" % lac)


def ressalva_127():
    f = {"data_impressao": "05/10/2026", "eventos": [E("02.01.2015", INI("FAXINA")), E("30.06.2015", FIM("FAXINA"))],
         "faltas": [{"data_fato": "03.06.2025", "grave": True, "situacao": "em apuração"}]}
    r = {"_incidentes": [{"tipo": "FALTA GRAVE", "complemento": "Data do fato: 03/02/2017", "data_decisao": "10/03/2017", "data_referencia": "03/02/2017",
                          "situacao": "CONCEDIDO"}]}
    _l, res = rf.quadro_trabalho(r, f, HOJE)
    it = res["rem_det"]["sem_atestado"]["itens"][0]
    ok("falta grave homologada (03/02/2017), falta grave registrada na ficha, sem homologação no RSPE (03/06/2025)" in it["base"]
       and "dos dias até a falta" in it["base"], "ressalva do art. 127: %s" % it["base"])


for nome, fn in [("em curso", em_curso_ate_impressao), ("estudo", estudo_ate_impressao), ("jornada", jornada_da_ficha),
                 ("simultâneos", simultaneos_uma_conta), ("transferência", unidade_corte_curto), ("resumo", resumo_pela_conciliacao),
                 ("cor", cor_amarela_e_seis_meses), ("baixa", baixa_com_outro_nome), ("liberação", liberacao_encerra_duplicado),
                 ("ESAJ", esaj), ("lacunas", lacunas), ("art. 127", ressalva_127)]:
    roda(nome, fn)
print("\n".join(falhas) if falhas else "ok: conferência D2 - remição (impressão da ficha, jornada, dias simultâneos, resumo pela conciliação, "
      "cor amarela, 6 meses, baixa com outro nome, liberação, ESAJ, lacunas, art. 127)")
sys.exit(1 if falhas else 0)
