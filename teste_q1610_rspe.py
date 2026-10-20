"""Quesitos de 16/10/2026, grupo "leitura do RSPE" (itens 18, 19, 20, 22, 23, 24, 26, 27, 28, 29, 30, 124 e 137), com casos
hipotéticos (nomes e números fictícios): lista de processos do evento cortada pelo SEEU, vínculo só pelo conteúdo (nunca pelo nome
do arquivo), rótulos "Extinta", "Arquivada" e "Sem início de cumprimento no SEEU", quadro "Cálculos da pena" ausente (some com o
RSPE juntado de novo igual), pena zero (pena da ação ou não informada), nascimento divergente RSPE x ficha, incompatibilidade de
regime como cumprimento, "(Indultada)" com comutação depois, violência presumida (art. 217-A), "Suspenso: Sim", medida de
segurança, RSPE gerado de novo no mesmo dia com conteúdo diferente e outras execuções da mesma pessoa como histórico.
Rodar: python teste_q1610_rspe.py"""
import copy
import json
import os
import shutil
import sys
import tempfile
import types
from datetime import date

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
wv = types.ModuleType("webview")
wv.SAVE_DIALOG, wv.FOLDER_DIALOG, wv.OPEN_DIALOG = 1, 2, 0
sys.modules.setdefault("webview", wv)
import rspe_scraper as rs  # noqa: E402
import rspe_auditoria as ra  # noqa: E402
import rspe_view as rv  # noqa: E402
import rspe_ficha as rf  # noqa: E402
import rspe_decretos as rd  # noqa: E402
import rspe_app as app  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)
    return cond


HOJE = date(2026, 10, 16)
P1, P2, P3 = "8800001-11.2019.8.12.0001", "8800002-22.2020.8.12.0001", "8800003-33.2021.8.12.0001"
EXEC = "7700001-00.2022.8.12.0001"


def crime(proc=P1, art="ART 155: Furto", lei="2848/40 - Código Penal", pena="2 ano(s), 0 mês(es) e 0 dia(s)", total="2a0m0d - PENA ORIGINÁRIA",
          fato="10/01/2019", **kw):
    c = {"processo_criminal": proc, "processo_situacao": "", "tipo_processo": "ACAO PENAL", "lei": lei, "artigo": art, "tipo_penal": "",
         "pena_imposta": pena, "pena_total_processo": total, "data_infracao": fato, "data_sentenca": "10/06/2019",
         "transito_processo": "10/08/2019", "transito_mp": "", "regime_sentenca": "Semiaberto", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "fracao_progressao": "16%",
         "fracao_livramento": "1/3", "extinto": "Não", "suspenso": "Não"}
    c.update(kw)
    return c


def ev(data, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", motivo="PRISÃO DEFINITIVA", procs=P1, **kw):
    e = {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": procs}
    e.update(kw)
    return e


def reg(crimes, eventos, incidentes=None, **kw):
    r = {"versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE, "nome": "FULANO DE TESTE", "processo_execucao": EXEC, "status_execucao": "ATIVO",
         "data_geracao_rspe": "15/10/2026", "pena_total": "2a0m0d", "pena_cumprida": "1a0m0d", "pena_remanescente": "1a0m0d",
         "regime_atual": "Semiaberto", "data_nascimento": "01/01/1990", "cpf": "", "nome_mae": "MAE DE TESTE", "arquivo": "x.pdf",
         "_crimes": crimes, "_eventos": eventos, "_incidentes": incidentes or [], "_acoes_sem_crime": []}
    r.update(kw)
    return rs.reprocessar(r)


def tipos(r, nivel=None):
    return {i["tipo"] for i in ra.auditar(r, HOJE)["aud_itens"] if nivel is None or i["nivel"] == nivel}


def itens(r, tipo):
    return [i for i in ra.auditar(r, HOJE)["aud_itens"] if i["tipo"] == tipo]


# ---------------- 18: lista de processos do evento cortada na margem ----------------
BLOCO = "Tipo: PRISÃO/INÍCIO DE CUMPRIMENTO\nMotivo: RECAPTURA\nData: 22/09/2026\nProcessos Selecionados: %s\n"
cortada = rs.blocos_tipo(BLOCO % ("%s, %s, %s," % (P1, P2, P3)))[0]
partida = rs.blocos_tipo(BLOCO % ("%s, %s, 8800003-" % (P1, P2)))[0]
inteira = rs.blocos_tipo(BLOCO % ("%s, %s, %s" % (P1, P2, P3)))[0]
ok(cortada.get("processos_incompletos") and partida.get("processos_incompletos"), "18: lista cortada (vírgula/número partido) marcada")
ok(not inteira.get("processos_incompletos"), "18: lista inteira não é marcada")
inc = rs.blocos_tipo("Tipo: SOMATÓRIO\n%s, %s,\nProcessos Selecionados: %s\n" % (P1, P2, P3))[0]
ok(not inc.get("processos_incompletos") and P3 in inc["processos"], "18: lista do incidente em duas linhas não é cortada: %s" % inc)
evs = [dict(partida)]
rs._completar_processos_eventos([crime(P3)], evs, [])
ok(evs[0]["processos"] == "" and evs[0]["processos_rspe"].startswith(P1), "18: lista incompleta não liga a prisão a processo: %s" % evs[0])
r = reg([crime(P1)], [ev("22/09/2026", procs="", processos_incompletos=True, processos_rspe="%s, %s," % (P1, P2))])
ok("lista-processos-incompleta-rspe" in tipos(r, "verificar"), "18: Auditoria avisa a lista incompleta")
ok(rs.periodos_custodia_detalhe(r["_eventos"])[0][3] == "", "18: custódia sem processo indicado")
ok(rs.reimportar_motivos({"versao_leitura_rspe": 4, "_eventos": [ev("01/01/2020", procs="%s, %s, %s" % (P1, P2, P3))]}),
   "18: registro da versão 4 com lista de 3 processos pede reimportação")
ok(not rs.reimportar_motivos({"versao_leitura_rspe": 4, "_eventos": [ev("01/01/2020")]}), "18: lista curta não pede reimportação")

# ---------------- 19: vínculo só pelo conteúdo, nunca pelo nome do arquivo ----------------
api = app.Api.__new__(app.Api)
info = {"PA": {"nome": app._norm("BELTRANO ALFA"), "mae": app._norm("MAE ALFA"), "cpf": "11111111111", "procs": {"1"}},
        "PB": {"nome": app._norm("CICRANO BETA"), "mae": app._norm("MAE BETA"), "cpf": "22222222222", "procs": {"2"}}}
fx = {"nome": "CICRANO BETA", "nome_mae": "MAE BETA", "cpf": "", "autos": [], "arquivo": "/pasta/BELTRANO ALFA.pdf"}
ok(api._vincular_ficha(fx, base=object(), info=info)[0] == "PB", "19: a ficha vincula pelo nome do conteúdo, não pelo do arquivo")
fx2 = dict(fx, nome="", nome_mae="", cpf="")
ok(api._vincular_ficha(fx2, base=object(), info=info)[0] == "", "19: sem dado no conteúdo, o nome do arquivo não vincula")

# ---------------- 20: rótulos Extinta, Arquivada, Sem início ----------------
r = reg([crime(extinto="Sim")], [ev("10/09/2019")])
ok(r["situacao_cumprimento"] == "EXTINTA" and r["situacao_eventos"] == "EM CUMPRIMENTO", "20: extinta: %s" % r["situacao_cumprimento"])
r = reg([crime()], [ev("10/09/2019"), ev("10/10/2020", "INTERRUPÇÃO", "FUGA", "")], status_execucao="ARQUIVADO")
ok(r["situacao_cumprimento"] == "ARQUIVADA" and rv.parada(r), "20: arquivada (regras seguem pelos eventos): %s" % r["situacao_cumprimento"])
ok("execucao-arquivada-com-pena" in tipos(r, "verificar"), "20: arquivada com pena por cumprir fica a conferir")
r = reg([crime()], [], pena_total="0a0m0d", pena_cumprida="0a0m0d", pena_remanescente="0a0m0d", regime_atual="")
ok(r["situacao_cumprimento"] == "SEM INÍCIO DE CUMPRIMENTO NO SEEU", "20: sem início: %s" % r["situacao_cumprimento"])
r = reg([crime()], [ev("10/09/2019"), ev("10/10/2020", "INTERRUPÇÃO", "FUGA", "")])
ok(r["situacao_cumprimento"].startswith("PENA INTERROMPIDA"), "20: execução ativa interrompida mantém o rótulo")

# ---------------- 22: quadro "Cálculos da pena" ausente ----------------
sem = dict(pena_total="", pena_cumprida="", pena_remanescente="", regime_atual="", termino_previsao_seeu="", data_base_seeu="")
r = reg([crime()], [ev("10/09/2019")], **sem)
ok(rs.sem_quadro_calculo(r) and [i for i in itens(r, "rspe-sem-quadro-calculo") if i["nivel"] == "verificar"], "22: sem o quadro: juntar de novo")
r = reg([crime()], [ev("10/09/2019")], _sem_calculo_confirmado="16/10/2026", **sem)
ok([i for i in itens(r, "rspe-sem-quadro-calculo") if i["nivel"] == "info"] and not [i for i in itens(r, "rspe-sem-quadro-calculo") if i["nivel"] != "info"],
   "22: RSPE juntado de novo igual: só nota")
ok(not rs.sem_quadro_calculo(reg([crime()], [ev("10/09/2019")])), "22: com o quadro, nada")

# ---------------- 23: pena zero ----------------
cs = [crime(P1, pena="0 ano(s), 0 mês(es) e 0 dia(s)", total="2a11m0d - PENA ORIGINÁRIA"),
      crime(P2, pena="0 ano(s), 0 mês(es) e 0 dia(s)", total="3a0m0d - PENA ORIGINÁRIA"), crime(P2, art="ART 180: Receptação")]
rs.penas_dos_crimes(cs)
ok(cs[0].get("pena_da_acao") and cs[0]["pena_imposta"] == "2a11m0d" and cs[0]["pena_imposta_rspe"].startswith("0 ano"), "23: único crime usa a pena da ação")
ok(cs[1].get("pena_nao_informada") and rs.pena_para_dias(cs[1]["pena_imposta"]) == 0, "23: vários crimes: pena não informada")
rs.penas_dos_crimes(cs)
ok(cs[0]["pena_imposta"] == "2a11m0d" and cs[0]["pena_imposta_rspe"].startswith("0 ano"), "23: refazer a análise é idempotente")
c28 = [crime(P3, art="ART 28: Porte de drogas para consumo", lei="11343/06 - Lei de Drogas", pena="0 ano(s), 0 mês(es) e 0 dia(s)", total="0a1m0d - PENA ORIGINÁRIA")]
rs.penas_dos_crimes(c28)
ok(not c28[0].get("pena_da_acao") and not c28[0].get("pena_nao_informada"), "23: art. 28 (sem pena privativa) fica como está")
out = {"indulto_2024": "POSSÍVEL: art. 9º, XV", "indulto_2024_status": "possivel", "comutacao_2024": "não atinge (1/4 até 25/12/2024)"}
rs._penas_a_verificar(out, cs, "2024", date(2024, 12, 25))
ok(out["indulto_2024"].startswith("A VERIFICAR: pena não informada") and out["indulto_2024_status"] == "verificar", "23: indulto a verificar: %s" % out)
ok(out["comutacao_2024"].startswith("não atinge"), "23: pena zero não muda o resultado desfavorável")
x = {"s": "cabe", "mot": "art. 1º, I"}
rd._incertezas_rspe({"data_referencia": "25/12/2023"}, {"_crimes": cs}, None, None, HOJE, x)
ok(x["s"] == "ver" and "pena não informada" in x["mot"], "23: decretos 2000-2023 a verificar: %s" % x)
r = reg([crime(P1, pena="0 ano(s), 0 mês(es) e 0 dia(s)", total="2a0m0d - PENA ORIGINÁRIA")], [ev("10/09/2019")])
ok([i for i in itens(r, "condenacao-sem-pena-imposta-no-rspe") if i["nivel"] == "info" and "pena da ação" in i["titulo"]], "23: Auditoria informa a pena da ação")

# ---------------- 24: nascimento RSPE x ficha ----------------
r = {"_crimes": [crime(fato="10/01/2010")], "data_nascimento": "01/03/1990"}
ok(rf.nascimento_muda_marco(r, date(1990, 3, 1), date(1988, 3, 1)), "24: a diferença muda os 21 anos no fato")
ok(not rf.nascimento_muda_marco(r, date(1990, 3, 1), date(1990, 2, 1)), "24: diferença que não muda marco")
r = reg([crime()], [ev("10/09/2019")])
dv = [i for i in ra.divergencias_fonte(r, {"data_nascimento": "01.01.1985", "cpf": "", "data_prisao": "10.09.2019"}) if i["tipo"] == "divergencia-siapen-nascimento"]
# conferência de 20/10/2026: sem efeito nos marcos, a divergência é informação; com efeito (_nasc_alt), fica a verificar
ok(dv and dv[0]["nivel"] == "info", "24: divergência SEEU x SIAPEN sem efeito: informação")
dv = [i for i in ra.divergencias_fonte(dict(r, _nasc_alt="01/01/1985"), {"data_nascimento": "01.01.1985", "cpf": "", "data_prisao": "10.09.2019"})
      if i["tipo"] == "divergencia-siapen-nascimento"]
ok(dv and dv[0]["nivel"] == "verificar", "24: divergência SEEU x SIAPEN que muda marco: verificar")
_orig = (rs.analise_decretos, rs.analise_decreto_2022)
try:
    rs.analise_decretos = lambda c, *a: {"indulto_2024": "não atinge (1/3 até 25/12/2024)" if c["data_nascimento"] == "01/01/1990"
                                         else "POSSÍVEL: art. 9º, § 2º (idade)"}
    rs.analise_decreto_2022 = lambda c, *a: {}
    rr = {"data_nascimento": "01/01/1990", "_nasc_alt": "01/01/1960", "indulto_2024": "não atinge (1/3 até 25/12/2024)", "indulto_2024_status": "nao"}
    rs.nascimento_divergente_decretos(rr, [], [], [], HOJE)
    ok(rr["indulto_2024_status"] == "verificar" and "nascimento divergente" in rr["indulto_2024"], "24: requisito de idade a verificar: %s" % rr)
    rr = {"data_nascimento": "01/01/1990", "indulto_2024": "não atinge (1/3 até 25/12/2024)", "indulto_2024_status": "nao"}
    rs.nascimento_divergente_decretos(rr, [], [], [], HOJE)
    ok(rr["indulto_2024_status"] == "nao", "24: sem divergência, nada muda")
finally:
    rs.analise_decretos, rs.analise_decreto_2022 = _orig

# ---------------- 26: incompatibilidade de regime conta como cumprimento ----------------
e26 = [ev("01/01/2020"), ev("01/06/2021", "INTERRUPÇÃO", "INCOMPATIBILIDADE DE REGIME", "")]
ok(rs.periodos_custodia(e26) == [(date(2020, 1, 1), None)], "26: incompatibilidade de regime não interrompe: %s" % rs.periodos_custodia(e26))
e26b = [ev("01/01/2020"), ev("01/06/2021", "INTERRUPÇÃO", "INTERRUPÇÃO DO CUMPRIMENTO DA PENA", "")]
ok(rs.periodos_custodia(e26b) == [(date(2020, 1, 1), date(2021, 6, 1))], "26: interrupção genérica segue cortando (a conferir)")
ok(len(rs.periodos_custodia_detalhe(e26)) == 1 and rs.periodos_custodia_detalhe(e26)[0][1] is None, "26: detalhe também segue")

# ---------------- 27: "(Indultada)" com comutação depois ----------------
r = reg([crime(P1, processo_situacao="Indultada, Comutada"), crime(P2)], [ev("10/09/2019")])
c1 = r["_crimes"][0]
ok(c1["extinto"] == "Sim" and c1.get("comutacao_posterior"), "27: segue extinto pelo indulto, com a comutação depois marcada")
ok([i for i in itens(r, "indultada-com-comutacao-posterior") if i["nivel"] == "info" and "conferir" in i["titulo"]], "27: nota na Auditoria")
r = reg([crime(P1, processo_situacao="Indultada"), crime(P2)], [ev("10/09/2019")])
ok(not r["_crimes"][0].get("comutacao_posterior"), "27: sem comutação, sem nota")

# ---------------- 28: violência no resumo e no relatório ----------------
c217 = crime(art="ART 217-A: Estupro de vulnerável", vga="N")
c121 = crime(art="ART 121: Homicídio simples", vga="N")
ok(rs.vga_resumo(c217) == "presumida" and rs.vga_resumo_txt(c217) == "violência presumida (art. 217-A)", "28: 217-A presumida, à parte")
ok(rs.vga_resumo(c121) == "S" and not rs.vga_indulto(c217), "28: homicídio pela elementar; 217-A fora da violência do indulto")
r = reg([c121, crime(P2)], [ev("10/09/2019")])
ok(r["vga"] == "S", "28: resumo do assistido com a violência elementar")
r = reg([c217], [ev("10/09/2019")])
ok(r["vga"] == "N" and r["vga_presumida"] == "S", "28: presumida à parte no resumo")
pa = rv.progressao_antecipada(r, None, {"prog_dias": 30, "prog": "15/11/2026"})
ok(any(x["ok"] is None and "Estupro de vulnerável (art. 217-A)" in x["txt"] for x in pa["pa_itens"]), "28: progressão antecipada mostra a presumida: %s" % pa)

# ---------------- 29: "Suspenso: Sim" ----------------
r = reg([crime(P1), crime(P2, suspenso="Sim")], [ev("10/09/2019")])
ok("crime-suspenso-a-verificar" in tipos(r, "verificar"), "29: crime suspenso a verificar")
out = {"comutacao_2024": "não atinge (1/4 até 25/12/2024)", "indulto_2024": "não atinge: sentença posterior à publicação"}
rs._penas_a_verificar(out, r["_crimes"], "2024", date(2024, 12, 25))
ok(out["comutacao_2024"].startswith("A VERIFICAR: \"Suspenso: Sim\""), "29: resultado pela pena fica a verificar: %s" % out)
ok(out["indulto_2024"].startswith("não atinge: sentença"), "29: resultado por outra causa não muda")

# ---------------- 30: medida de segurança ----------------
cms = [crime(P1, pena="", total="1a0m0d - MEDIDA DE SEGURANÇA", regime_sentenca="Indefinido")]
rs.penas_dos_crimes(cms)
ok(cms[0].get("medida_seguranca") and rs.pena_para_dias(cms[0]["pena_imposta"]) == 0, "30: o prazo mínimo não entra como pena: %s" % cms[0])
r = reg([crime(P1, pena="", total="1a0m0d - MEDIDA DE SEGURANÇA"), crime(P2)], [ev("10/09/2019")])
ok("medida-de-seguranca-na-execucao" in tipos(r, "verificar"), "30: Auditoria: a verificar")
ok(sum(rs.pena_para_dias(c.get("pena_imposta") or c.get("pena_total_processo")) or 0 for c in r["_crimes"]) == 2 * 365, "30: fora da soma")
out = {"indulto_2025": "POSSÍVEL: art. 9º, I", "indulto_2025_status": "possivel"}
rs._penas_a_verificar(out, r["_crimes"], "2025", date(2025, 12, 25))
ok(out["indulto_2025_status"] == "verificar" and "medida de segurança" in out["indulto_2025"], "30: indulto a verificar")

# ---------------- 124: RSPE gerado de novo no mesmo dia; 22: confirmação do cálculo ausente ----------------
d = tempfile.mkdtemp()
_pa, _ex = app.pasta_app, app._extrair_com_hash
try:
    app.pasta_app = lambda: d
    base = app.Base(os.path.join(d, "t.sqlite"))
    r1 = reg([crime()], [ev("10/09/2019")])
    r1["_hash"] = "h1"
    base.gravar(r1)
    r2 = copy.deepcopy(r1)
    r2["_hash"] = "h2"
    r2["_incidentes"].append({"tipo": "PROGRESSÃO DE REGIME", "situacao": "CONCEDIDO", "complemento": "Progressão para o Semiaberto",
                              "data_decisao": "15/10/2026", "data_referencia": "15/10/2026", "processos": ""})
    r3 = copy.deepcopy(r1)
    r3["_hash"] = "h3"
    lote = {"a.pdf": r2, "b.pdf": r3}
    app._extrair_com_hash = lambda a: copy.deepcopy(lote[os.path.basename(a)])
    api = app.Api.__new__(app.Api)
    api._js = lambda *a, **k: None
    res = api._lote_([os.path.join(d, "b.pdf")], base, True)
    ok(res["duplicados"] == 1 and len(base.historico(EXEC)) == 1, "124: mesmo dia e mesmo conteúdo (outro arquivo): já na base")
    res = api._lote_([os.path.join(d, "a.pdf")], base, True)
    h = base.historico(EXEC)
    ok(res["atualizados"] == 1 and len(h) == 2 and "substituído" in h[0]["geracao"] and h[1]["dados"]["_hash"] == "h2",
       "124: conteúdo diferente substitui e guarda o anterior: %s %s" % (res, [x["geracao"] for x in h]))
    ok(base.um(EXEC)["_hash"] == "h2", "124: a base fica com o RSPE novo")
    reg_ = api._falhas_lote_auto["registro"][0]
    ok(any("conteúdo diferente" in o for o in reg_["obs"]) and reg_["arquivo"] == "a.pdf", "124: registro da importação diz a substituição: %s" % reg_)
    # 22: RSPE sem o quadro, juntado de novo (outro arquivo) e ainda sem o quadro: confirma, e o alerta vira nota
    s1 = reg([crime(P2)], [ev("10/09/2019", procs=P2)], processo_execucao="7700002-00.2022.8.12.0001", **sem)
    s1["_hash"] = "s1"
    base.gravar(s1)
    s2 = copy.deepcopy(s1)
    s2["_hash"] = "s2"
    lote["c.pdf"] = s2
    api._lote_([os.path.join(d, "c.pdf")], base, True)
    g = base.um("7700002-00.2022.8.12.0001")
    ok(g.get("_sem_calculo_confirmado"), "22: novo RSPE igual, sem o quadro: confirmado")
    ok(not [i for i in itens(rs.reprocessar(g), "rspe-sem-quadro-calculo") if i["nivel"] != "info"], "22: depois de juntado de novo, só nota")
    base.con.close()
finally:
    app.pasta_app, app._extrair_com_hash = _pa, _ex
    shutil.rmtree(d, ignore_errors=True)

# ---------------- 137: outras execuções como histórico; reincidência só a conferir ----------------
o = reg([crime(P3, fato="10/01/2015", transito_processo="10/08/2016")], [ev("01/02/2016", procs=P3), ev("01/02/2017", "INTERRUPÇÃO", "CUMPRIMENTO DA PENA", "")],
        [{"tipo": "FALTA GRAVE", "situacao": "CONCEDIDO", "complemento": "Homologação de falta grave", "data_decisao": "10/10/2016",
          "data_referencia": "05/10/2016", "processos": ""}], processo_execucao="7700009-00.2016.8.12.0001", status_execucao="ARQUIVADO")
hist = app._historico_exec(o)
ok("prisões 01/02/2016 a 01/02/2017" in hist and "faltas" in hist, "137: histórico da outra execução: %s" % hist)
r = reg([crime(P1, fato="10/01/2019")], [ev("10/09/2019")])
r["_outras_condenacoes"] = [dict(c, _execucao=o["processo_execucao"]) for c in o["_crimes"]]
r["_outras_execucoes"] = [{"processo": o["processo_execucao"], "status": "ARQUIVADO", "encerrada": True, "crimes": "art. 155 CP", "geracao": "",
                           "tem_crime": False, "historico": hist}]
it = ra.auditar(r, HOJE)["aud_itens"]
ok([i for i in it if i["tipo"] == "reincidente-pela-lei-sem-marcacao" and "outra execução" in i["titulo"] and i["nivel"] == "verificar"],
   "137: condenação de outra execução: reincidência a conferir")
ok([i for i in it if i["tipo"] == "outras-execucoes" and "a conferir" in i["detalhe"] and "prisões" in i["detalhe"]], "137: histórico na Auditoria")

if falhas:
    print("FALHOU (quesitos 16/10, leitura do RSPE):")
    for f_ in falhas:
        print("  " + f_)
    sys.exit(1)
print("ok: quesitos 16/10 - leitura do RSPE (itens 18, 19, 20, 22, 23, 24, 26, 27, 28, 29, 30, 124 e 137)")
