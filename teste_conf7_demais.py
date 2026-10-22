"""Segunda conferência independente (7.14.6), frente remição, progressão, auditoria e prescrição: estudo pedido só depois do último
semestre certificado; ressalva do art. 127 no pedido de atestado de trabalho anterior a falta grave; fim suposto do setor encerrado
só pelo início de outro (baixa tardia); sanção disciplinar registrada sem o lançamento da falta; roubo com lesão grave (art. 157,
§ 3º, I) sem resultado morte; monitoramento eletrônico desta execução tratado como interrupção pelo SEEU; blocos "2/5" e "40%"
separados na detração antes da fração; pena "Suspenso: Sim" presa por outro processo (art. 116, p. ú.); contravenção posterior
não interrompe a prescrição do crime (art. 117, VI).
Casos hipotéticos, nomes fictícios. Rodar: python teste_conf7_demais.py"""
import copy
import sys
import types
from datetime import date
from fractions import Fraction

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf
import rspe_prescricao as rp
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 21)
P1, P2 = "0000001-11.2020.8.12.0001", "0000002-22.2025.8.12.0001"
PEXEC = "6000009-99.2023.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def FD(eventos, impressao="05/10/2026"):
    f = {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}
    return rf.derivar(f, [dict(e, d=rf._dp(e["data"])) for e in f["eventos"]])


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto", "tipo_penal": "CAPUT: Subtrair",
         "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2021", "data_denuncia": "10/03/2021",
         "data_sentenca": "10/06/2021", "transito_mp": "10/07/2021", "transito_processo": "10/07/2021", "extinto": "Não", "suspenso": "Não",
         "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
         "fracao_progressao": "1/6 - Comum", "fracao_livramento": "1/3 - Comum", "regime_sentenca": "Fechado", "hediondo_ou_equiparado": "N"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, processos=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": processos}


def reg(crimes, eventos=(), **kw):
    r = {"nome": "Teste Ficticio", "regime_atual": "Fechado - ATIVO", "pena_total": "2a0m0d", "pena_cumprida": "0a6m0d",
         "pena_remanescente": "1a6m0d", "data_geracao_rspe": "01/10/2026", "data_base_seeu": "", "_crimes": crimes,
         "_incidentes": [], "_eventos": list(eventos), "data_nascimento": "01/01/1980", "status_execucao": "ATIVO", "processo_execucao": PEXEC}
    r.update(kw)
    return r


PR, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"

# ---- 1: estudo pedido só depois do último semestre certificado (não desde a matrícula) ----
N1 = {"R": {"ult_dec": date(2026, 8, 31)}, "post": [], "impressao": date(2026, 10, 2), "est_cert_fim": date(2026, 6, 30)}
f1 = {"estudos": [{"curso": "SETOR ESCOLAR", "inicio": "02.04.2026", "fim": ""}], "eventos": []}
res1 = rf._res_fundamentacao(N1, {"linhas": []}, f1, HOJE)
t1 = rf.fundamentacao_remicao(res1)
ok("Setor Escolar (01/07/2026 em diante)" in t1, "1: estudo desde a matrícula, e não depois do semestre certificado: %s" % t1[:300])
ok("02/04/2026" not in t1, "1: pede de novo o semestre já certificado: %s" % t1[:300])
# sem certidão: a última decisão de remição continua o corte
N1b = dict(N1, est_cert_fim=None)
t1b = rf.fundamentacao_remicao(rf._res_fundamentacao(N1b, {"linhas": []}, f1, HOJE))
ok("(01/09/2026 em diante)" in t1b, "1b: sem certidão, o corte é a última decisão: %s" % t1b[:300])

# ---- 2: pedido de atestado de trabalho anterior a falta grave homologada: ressalva do art. 127 ----
T2 = {"linhas": [{"st": "sem", "pedir_dias": 15.0, "pedir_trechos": [(date(2019, 10, 24), date(2020, 1, 30))], "pedir_ini": date(2019, 10, 24),
                  "pedir_fim": date(2020, 1, 30), "local": "Artesanato", "em_curso": False, "fim": date(2020, 1, 30)}]}
N2 = {"R": {"ult_dec": None}, "post": [], "impressao": date(2026, 10, 2), "faltas_127": [(date(2020, 2, 19), "falta grave homologada (19/02/2020)")]}
r2 = rf._res_fundamentacao(N2, T2, {"estudos": [], "eventos": []}, HOJE)
ok("19/02/2020" in r2["ressalva_127_trab"], "2: ressalva ausente: %s" % r2["ressalva_127_trab"])
t2 = rf.fundamentacao_remicao(r2)
ok("perda de até 1/3 (LEP, art. 127)" in t2 and "Artesanato, 24/10/2019 a 30/01/2020" in t2, "2: fundamentação sem a ressalva: %s" % t2[:500])
N2b = dict(N2, faltas_127=[(date(2019, 1, 5), "falta grave homologada (05/01/2019)")])
ok(not rf._res_fundamentacao(N2b, T2, {"estudos": [], "eventos": []}, HOJE)["ressalva_127_trab"], "2b: falta anterior ao trabalho não gera ressalva")

# ---- 3: setor encerrado só pelo início de outro, com a baixa lançada na saída da unidade: fim suposto, com a baixa da ficha ----
I_ = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento 1."
F_ = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento , motivo: %s."
f3 = FD([("15.01.2024", I_ % "MANUTENÇÃO PREDIAL - PINTOR"), ("14.08.2024", I_ % "OBRAS EXTERNAS LTDA"),
         ("07.11.2025", F_ % ("MANUTENÇÃO PREDIAL - PINTOR", "Saida do Presídio")), ("11.11.2025", F_ % ("OBRAS EXTERNAS LTDA", "Saida do Presídio"))])
t3 = [t for t in f3["trabalho"] if "PINTOR" in t["setor"]]
ok(t3 and t3[0]["fim"] == "14.08.2024" and t3[0].get("baixa_tardia") == "07.11.2025", "3: baixa tardia não registrada: %s" % t3)
import rspe_remicao as rrm
T3 = rrm.trabalho_x_atestados(f3, HOJE, None, None, None)
L3 = [L for L in T3["linhas"] if "Pintor" in L["local"]]
ok(L3 and "fim suposto" in L3[0]["periodo"] and "07/11/2025" in L3[0]["periodo"], "3: linha sem o fim suposto: %s" % [L["periodo"] for L in L3])

# ---- 4: sanção disciplinar registrada sem o lançamento da falta (isolamento em cela): falta a apurar ----
f4 = FD([("10.02.2025", "Nesta data o interno iniciou no Setor Escolar."),
         ("15.05.2025", "Mudança de Cela: UNIDADE X, Motivo: SANCIOANDO - CI 47/2025/CDE/UX, Origem: R I/C12, Destino: R VI/C-B01, Conforme Documento: CI 47."),
         ("15.05.2025", "Nesta data o interno deixa de estudar por estar sancionado, respondendo por falta disciplinar."),
         ("24.05.2025", "Mudança de Cela: UNIDADE X, Motivo: TERMINO DO SANCIONAMENTO, Origem: R VI/C-B01, Destino: R III/C08, Conforme Documento: N/C.")])
fx4 = f4["faltas"]
ok(len(fx4) == 1 and fx4[0]["data_fato"] == "15.05.2025" and fx4[0]["grave"] and fx4[0].get("sancao_sem_registro"), "4: sanção não lida como falta: %s" % fx4)
r4 = reg([crime(data_infracao="26/06/2024")], [ev(PR, "PRISÃO EM FLAGRANTE", "26/06/2024")])
rs.faltas_da_ficha(r4, f4, HOJE)
i4 = [i for i in r4["_incidentes"] if i.get("_ficha")]
ok(i4 and "natureza e homologação não constam" in i4[0]["complemento"] and not i4[0].get("_data_ciencia"), "4: incidente: %s" % i4)
f4b = FD([("15.05.2025", "Nesta data o interno deixa de estudar por estar sancionado, respondendo por falta disciplinar.")])
ok(f4b["faltas"] and not f4b["faltas"][0]["grave"], "4b: sem isolamento, a natureza fica desconhecida (não grave): %s" % f4b["faltas"])

# ---- 5: roubo com lesão grave (art. 157, § 3º, I) não tem resultado morte: saída temporária sem dúvida indevida ----
c5 = crime(artigo="ART 157: Roubo", tipo_penal="§ 3º, I: Se da violência resulta lesão corporal grave", hediondo_ou_equiparado="S",
           data_infracao="21/12/2023", resultado_morte="N", vga="S")
ok(not rv._morte_tipo(c5), "5: § 3º, I tratado como resultado morte")
ok(rv._morte_tipo(dict(c5, tipo_penal="§ 3º, II: Se resulta morte")), "5: latrocínio (§ 3º, II) deixou de ser conferido")

# ---- 6: monitoramento eletrônico desta execução que o RSPE trata como interrupção: verificar, com a estimativa ----
c6 = crime(pena_imposta="5 ano(s), 0 mês(es) e 0 dia(s)", fracao_progressao="40% - Art.112, V, da LEP", data_infracao="01/07/2019")
r6 = reg([c6], [ev(PR, "PRISÃO EM FLAGRANTE", "30/07/2019"), ev(INT, "LIBERDADE PROVISÓRIA", "20/12/2020"),
                ev(PR, "INÍCIO DO CUMPRIMENTO REGIME FECHADO", "30/01/2026")],
         data_base_seeu="30/01/2026", progressao_previsao_seeu="22/07/2027", pena_total="5a0m0d")
f6 = {"data_impressao": "02/10/2026", "eventos": [
    {"data": "15.02.2024", "texto": "Entrada na Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Procedente: DECISÃO JUDICIAL - INTERIOR, Conforme OF/CI %s." % PEXEC},
    {"data": "15.02.2024", "texto": "Entrando na monitoração em: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Conforme Ofício: %s" % PEXEC},
    {"data": "04.02.2026", "texto": "Saída da Unidade Penal: UNIDADE MISTA DE MONITORAMENTO VIRTUAL ESTADUAL, Destino: PENITENCIÁRIA X, Motivo: Regressão de Regime, Conforme: %s." % PEXEC}]}
i6 = rf._monitoramento_x_ficha(r6, f6)
ok(len(i6) == 1 and i6[0]["nivel"] == "verificar" and "715 dias" in i6[0]["titulo"], "6: item do monitoramento: %s" % i6)
ok(i6 and i6[0].get("prog_estimada") == rs.fmt(date(2027, 7, 22) - __import__("datetime").timedelta(days=286)), "6: estimativa: %s" % (i6 and i6[0].get("prog_estimada")))
f6b = copy.deepcopy(f6)
for e in f6b["eventos"]:
    e["texto"] = e["texto"].replace(PEXEC, "0000777-77.2023.8.12.0001")
ok(not rf._monitoramento_x_ficha(r6, f6b), "6b: monitoramento de outro processo virou cumprimento desta execução")
f6c = copy.deepcopy(f6)
for e in f6c["eventos"]:
    e["texto"] = e["texto"].replace(PEXEC, P1)
i6c = rf._monitoramento_x_ficha(r6, f6c)
ok(i6c and "cautelar" in i6c[0]["titulo"] and "Tema 1155" in i6c[0]["detalhe"], "6c: monitoramento pela ação penal sem a detração: %s" % i6c)
# entrada no monitoramento depois de descumprimento das condições: a saída da unidade só registra a recaptura - sem item
r6d = copy.deepcopy(r6)
r6d["_eventos"][1]["motivo"] = "DESCUMPRIMENTO DAS CONDIÇÕES"
ok(not rf._monitoramento_x_ficha(r6d, f6), "6d: monitoramento depois de descumprimento virou cumprimento")

# ---- 7: blocos "2/5" e "40%" do SEEU separados: a detração no bloco certo ----
c7a = crime(pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", fracao_progressao="40% - Art.112, V, da LEP", processo_criminal=P2)
c7b = crime(pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", fracao_progressao="2/5 - Hediondo Primario")
r7 = reg([c7a, c7b], seeu_fracoes_progressao=["Hediondo primário (2/5): 1a10m22d", "Hediondo primário (40%): 2a4m23d"])
b7 = ra._detracao_blocos(r7, [c7a, c7b])
ok(b7 and len(b7) == 2 and [b[6] for b in b7 if b[3] >= 10] == ["2/5"], "7: blocos: %s" % b7)
t7 = ra._texto_blocos(b7) if b7 else ""
ok("no bloco de 2/5 (pena de 6 anos)" in t7 and "no bloco de 40% (pena de 6 anos), fração sobre a pena inteira" in t7, "7: texto: %s" % t7[:400])

# ---- 8: pena "Suspenso: Sim" (art. 28) e prisão só por outro processo: suspende (art. 116, p. ú.), não "em cumprimento" ----
c8a = crime(processo_criminal=P1, artigo="ART 213: Estupro", pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="29/11/2016",
            data_denuncia="09/07/2018", data_sentenca="23/10/2020", transito_mp="07/06/2023", transito_processo="07/06/2023")
c8b = crime(processo_criminal=P2, lei="11343/06 - Lei de Drogas", artigo="ART 28: Posse para consumo", tipo_penal="CAPUT, II: Quem adquirir",
            pena_imposta="0 ano(s), 6 mês(es) e 0 dia(s)", data_infracao="26/09/2022", data_denuncia="11/09/2024", data_sentenca="15/01/2026",
            transito_mp="27/01/2026", transito_processo="02/02/2026", suspenso="Sim")
r8 = reg([c8a, c8b], [ev(PR, "PRISÃO DEFINITIVA", "07/02/2024", P1)], pena_total="6a0m0d")
L8 = [L for L in rp.analisar(copy.deepcopy(r8), HOJE)["presc_linhas"] if L.get("proc_crim") == P2]
ok(L8 and "art. 116, p. único" in L8[0]["ppe_detalhe"] and "Suspenso: Sim" in L8[0]["ppe_detalhe"] and "em cumprimento" not in L8[0]["ppe_status"],
   "8: %s | %s" % (L8 and L8[0]["ppe_status"], L8 and L8[0]["ppe_detalhe"][:600]))

# ---- 9: contravenção posterior não interrompe a prescrição do crime (art. 117, VI) ----
c9a = crime(artigo="ART 147: Ameaça", tipo_penal="CAPUT: Ameaçar", pena_imposta="0 ano(s), 1 mês(es) e 10 dia(s)", data_infracao="26/07/2022",
            data_denuncia="10/08/2022", data_sentenca="26/10/2022", transito_mp="29/08/2023", transito_processo="29/08/2023")
c9b = crime(processo_criminal=P2, lei="3688/41 - Lei das Contravenções Penais", artigo="ART 19: Porte de arma", tipo_penal="CAPUT: Trazer consigo arma",
            pena_imposta="0 ano(s), 0 mês(es) e 18 dia(s)", data_infracao="19/01/2024", data_denuncia="21/05/2025", data_sentenca="15/08/2025",
            transito_mp="26/09/2025", transito_processo="01/10/2025")
L9 = [L for L in rp.analisar(reg([c9a, c9b]), HOJE)["presc_linhas"] if L.get("proc_crim") == P1]
ok(L9 and "Novo crime em 19/01/2024" not in L9[0]["ppe_detalhe"] and "Contravenção em 19/01/2024" in L9[0]["ppe_detalhe"],
   "9: contravenção tratada como novo crime: %s" % (L9 and L9[0]["ppe_detalhe"][:700]))
ok(L9 and "28/08/2026" in L9[0]["ppe_detalhe"] + L9[0]["ppe_status"], "9: data-limite sem a interrupção: %s" % (L9 and L9[0]["ppe_status"]))

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("teste_conf7_demais: ok")
