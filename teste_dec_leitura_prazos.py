"""Teste de regressão: decisões sobre os pareceres da 7.15.2, frente "leitura e prazos" (P01 a P07, P45 a P51 e as linhas S1xxx e
S8xxx do P57). Casos sintéticos, com nomes e números fictícios.
P01  falta dos 12 meses contada até hoje no livramento (a coluna Falta continua o retrato do RSPE).
P02  coluna Término com a data do SEEU e "⚠" quando passa do limite do art. 75; o máximo na dica.
P03  planilha "Completo" com as duas datas-base (a gravada e a da tela), com rótulo e motivo.
P04  escala de prioridade de 1 a 7 retirada.
P05  homicídio simples com o selo de hediondo: "hediondo a verificar (grupo de extermínio não informado)" no resumo do crime.
P07  homicídio do § 2º-D com o selo: "hediondo a verificar" no resumo e ponto a verificar na Auditoria.
P45  continuado prescrito em todas as frações do acréscimo: vermelho.
P46  prescrição que só aparece pela tese "só a prisão suspende": amarelo, com as duas contas.
P47  art. 28 da Lei de Drogas como base de reincidência em outra linha: aviso do Tema 506.
P48  revogação do sursis: termo inicial na data da decisão, com o trânsito como hipótese a verificar.
P50  tempo em livramento não suspenso de outra execução: não se propõe detração; aviso a verificar.
P57  S1010/S1012 (SV 56: o rótulo da situação traz a ressalva), S1042 (Responde PADIC não é conduta ruim), S8027 (pena cumprida pela
     detração não lançada: o fundamento é o cumprimento, não a prescrição "aparente").
Rodar: python teste_dec_leitura_prazos.py (sai com código 1 se algum caso falhar)."""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs  # noqa: E402
import rspe_prescricao as rp  # noqa: E402
import rspe_view as rv  # noqa: E402
import rspe_auditoria as ra  # noqa: E402

HOJE = date(2026, 11, 5)
rv.HOJE = HOJE
falhas = []
FURTO = "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., Reclusão: 1 a 4 anos E Multa"
P1, P2 = "0000101-11.2011.8.12.0001", "0000202-22.2012.8.12.0001"
PRI, INT = "PRISÃO/INÍCIO DE CUMPRIMENTO", "INTERRUPÇÃO"


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def pena(a, m=0, d=0):
    return "%d ano(s), %d mês(es) e %d dia(s)" % (a, m, d)


def crime(**kw):
    c = {"processo_criminal": P1, "data_infracao": "01/01/2012", "data_denuncia": "01/02/2012", "data_sentenca": "01/06/2012",
         "transito_mp": "01/09/2012", "transito_processo": "01/09/2012", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": FURTO, "pena_imposta": pena(1), "pena_total_processo": "%s - PENA ORIGINÁRIA" % pena(1),
         "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não", "fracao_progressao": "1/6 - Comum",
         "fracao_livramento": "1/3 - Comum Primário", "vga": "N", "resultado_morte": "N"}
    c.update(kw)
    return c


def ev(data, motivo, tipo=PRI, proc=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": proc}


def inc(tipo, data, comp="", ref=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": comp, "data_decisao": data, "data_referencia": data if ref is None else ref, "situacao": sit,
            "processos": ""}


def reg(crimes, eventos=(), incidentes=(), **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": "01/01/1980",
         "data_geracao_rspe": "01/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO", "processo_execucao": "0009999-99.2011.8.12.0001"}
    r.update(kw)
    return r


# ---------------- P01: falta dos 12 meses até hoje no livramento ----------------
# falta homologada em 15/10/2025: na emissão do RSPE (01/10/2026) ainda nos 12 meses; hoje (05/11/2026), fora
r = reg([crime(pena_imposta=pena(8), pena_total_processo="8a0m0d")], [ev("01/01/2020", "PRISÃO DEFINITIVA", proc=P1)],
        [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "01/01/2020", "Fechado - Regime Inicial"),
         inc("HOMOLOGAÇÃO DE FALTA GRAVE", "20/10/2025", "Falta grave em 15/10/2025", ref="15/10/2025")],
        livramento_previsao_seeu="01/09/2026", pena_total="8a0m0d")
r.update(rs.faltas(r, r["_eventos"], r["_incidentes"], rs.to_date("01/10/2026"), r["_crimes"]))
confere(r["falta_12m"] == "SIM", "P01: falta nos 12 meses na emissão do RSPE: %s" % r.get("falta_12m"))
fal, det = rv.falta_12m_detalhe_hoje(r, HOJE)
confere(fal != "SIM", "P01: contada até hoje, a falta já saiu dos 12 meses: %s" % fal)
sit = rv._vencido_pedido(r, ("Vencido há 65 dias · x", "vencido"), date(2026, 9, 1), "LIVRAMENTO")
confere("sem pedido no RSPE - requerer" in sit[0], "P01: livramento vencido sem a falta de hoje: requerer: %s" % (sit,))
sit = rv._vencido_pedido(r, ("Vencido há 65 dias · x", "vencido"), date(2026, 9, 1), "PROGRESS")
confere("requerer" not in sit[0], "P01: a progressão segue o retrato do RSPE (só o livramento mudou): %s" % (sit,))
full = rv._vencido_full(r, "Vencido", "vencido", "LIVRAMENTO")
confere("já saiu da janela do art. 83, III, b" in full and "Falta nos últimos 12 meses:" not in full, "P01: dica do livramento: %s" % full)

# ---------------- P02: coluna Término com a data do SEEU e "⚠" ----------------
c30 = [crime(pena_imposta=pena(25), data_infracao="10/01/2015", transito_processo="01/01/2016", transito_mp="01/01/2016"),
       crime(processo_criminal=P2, pena_imposta=pena(20), data_infracao="12/01/2015", transito_processo="01/01/2016", transito_mp="01/01/2016")]
r = reg(c30, [ev("15/01/2015", "PRISÃO EM FLAGRANTE")], [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "15/01/2015", "Fechado - Regime Inicial")],
        pena_total="45a0m0d", termino_previsao_seeu="15/01/2060", data_base_seeu="15/01/2015")
m = rv.modelo(copy.deepcopy(r), {}, None, [])
confere(m["termino"] == "15/01/2060 ⚠", "P02: coluna com a data do SEEU e o sinal: %s" % m["termino"])
confere("14/01/2045" in (m.get("termino_full") or "") and "art. 75" in m["termino_full"], "P02: máximo na dica: %s" % m.get("termino_full"))
_it = next((i for i in m["aud_itens"] if i.get("tipo") == "limite-de-cumprimento-art-75"), {})
confere("mantém a data do SEEU" in (_it.get("detalhe") or ""), "P02: texto da Auditoria sobre a coluna: %s" % _it.get("detalhe"))

# ---------------- P03: planilha "Completo" com as duas datas-base ----------------
import rspe_export as rx  # noqa: E402
cols = rx.colunas_completo()
confere(cols.index("data_base_tela") == cols.index("data_base") + 1 and "data_base_tela_motivo" in cols, "P03: colunas: %s" % cols[:20])
lin = rx.linha_completo({"_bruto": {"data_base": "20/02/2025", "nome": "X"}, "db": "05/01/2025", "db_motivo": "data da falta grave"})
confere(lin[cols.index("data_base")] == "20/02/2025" and lin[cols.index("data_base_tela")] == "05/01/2025"
        and lin[cols.index("data_base_tela_motivo")] == "data da falta grave", "P03: valores: %s" % lin)
confere("gravada" in rx.COMPLETO_TITULOS["data_base"] and "tela" in rx.COMPLETO_TITULOS["data_base_tela"], "P03: rótulos")

# ---------------- P04: escala de prioridade retirada ----------------
confere(not hasattr(rv, "prioridade") and not hasattr(rv, "aplicar_prioridade") and not hasattr(rv, "PRIO_NIVEIS"), "P04: escala ainda presente")

# ---------------- P05 e P07: selo de hediondo a verificar ----------------
HOM = dict(lei="2848/40 - Código Penal", artigo="ART 121: Homicídio", pena_imposta=pena(20), fracao_progressao="40% - Hediondo",
           fracao_livramento="2/3 - Hediondo", hediondo_ou_equiparado="S", vga="S", resultado_morte="S", data_infracao="10/06/2026")
c5 = crime(tipo_penal="CAPUT: Matar alguem, Reclusão: 6 a 20 anos", **HOM)
confere(rs.hediondo_selo_verificar(c5) == "hediondo a verificar (grupo de extermínio não informado)", "P05: %s" % rs.hediondo_selo_verificar(c5))
c7 = crime(tipo_penal="§ 2º-D: homicídio por integrante de organização criminosa ultraviolenta, Reclusão: 20 a 40 anos", **HOM)
confere(rs.hediondo_selo_verificar(c7).startswith("hediondo a verificar (§ 2º-D"), "P07: %s" % rs.hediondo_selo_verificar(c7))
c2q = crime(tipo_penal="§ 2º: homicídio qualificado, inciso II: motivo fútil, Reclusão: 12 a 30 anos", **HOM)
confere(rs.hediondo_selo_verificar(c2q) == "", "P05/P07: o qualificado do § 2º é hediondo, sem ressalva: %s" % rs.hediondo_selo_verificar(c2q))
c7s = crime(tipo_penal="§ 2º-D: homicídio por integrante de organização criminosa ultraviolenta, Reclusão: 20 a 40 anos",
            **dict(HOM, fracao_progressao="25% - Comum", fracao_livramento="1/3 - Comum", hediondo_ou_equiparado="N"))
confere(rs.hediondo_selo_verificar(c7s) == "", "P07: sem o selo, não há o que ressalvar: %s" % rs.hediondo_selo_verificar(c7s))
r = reg([c7], [ev("10/06/2026", "PRISÃO EM FLAGRANTE")], pena_total="20a0m0d")
its = [i for i in ra.auditar(r, HOJE)["aud_itens"] if i.get("tipo") == "homicidio-2d-com-selo-de-hediondo"]
confere(len(its) == 1 and its[0]["nivel"] == "verificar" and "15.358" in its[0]["detalhe"], "P07: Auditoria: %s" % its)
m = rv.modelo(copy.deepcopy(reg([c5], [ev("10/06/2026", "PRISÃO EM FLAGRANTE")], pena_total="20a0m0d")), {}, None, [])
confere(m["crimes_det"][0]["hediondo_txt"].startswith("hediondo a verificar"), "P05: resumo do crime: %s" % m["crimes_det"][0].get("hediondo_txt"))

# ---------------- P45: continuado prescrito em todas as frações: vermelho ----------------
c45 = crime(data_infracao="01/01/2014", data_denuncia="01/02/2014", data_sentenca="01/03/2019", transito_mp="01/05/2019",
            transito_processo="01/05/2019", pena_imposta=pena(2, 4), tipo_penal=FURTO + " (ART. 71 - CRIME CONTINUADO)")
L = rp.analisar(reg([c45]), HOJE)["presc_linhas"][0]
confere(L["retro_cor"] == "vermelho" and "em qualquer fração" in L["retro_status"] and "Súmula 497" in L["retro_status"],
        "P45: punitiva em todas as frações: %s / %s" % (L["retro_status"], L["retro_cor"]))
# só a partir de certa fração: continua amarelo (pena de 3 anos e 6 meses: sem o acréscimo, 2a6m a 3a0m - 1/6 dá 3 anos, prazo 8)
c45b = dict(c45, pena_imposta=pena(4, 6))
L = rp.analisar(reg([c45b]), HOJE)["presc_linhas"][0]
confere(L["retro_cor"] != "vermelho" or "em qualquer fração" in L["retro_status"],
        "P45b: vermelho só com todas as frações prescritas: %s / %s" % (L["retro_status"], L["retro_cor"]))

# ---------------- P46: tese "só a prisão suspende": amarelo, com as duas contas ----------------
A = crime(pena_imposta=pena(8), pena_total_processo="8a0m0d")
B = crime(processo_criminal=P2, data_infracao="01/03/2018", data_denuncia="01/04/2018", data_sentenca="01/08/2018", transito_mp="01/03/2019",
          transito_processo="01/03/2019")
r46 = reg([A, B], [ev("01/10/2012", "PRISÃO DEFINITIVA", proc=P1), ev("01/01/2018", "LIVRAMENTO CONDICIONAL", tipo=INT)],
          [inc("LIVRAMENTO CONDICIONAL", "01/01/2018", "Livramento condicional")], situacao_cumprimento="EM CUMPRIMENTO (livramento condicional)")
L = next(x for x in rp.analisar(r46, HOJE)["presc_linhas"] if x["proc_crim"] == P2)
confere(L["ppe_cor"] == "amarelo" and "tese defensiva" in L["ppe_status"] and "28/02/2023" in L["ppe_status"] and "HC 429.545" in L["ppe_status"],
        "P46: as duas contas, em amarelo: %s / %s" % (L["ppe_status"], L["ppe_cor"]))
confere(L.get("ppe_tese_stj") and "Conclusão ajustada" in L["ppe_detalhe"], "P46: conta pela posição do STJ guardada")

# ---------------- P47: art. 28 como base de reincidência ----------------
c28 = crime(processo_criminal=P2, lei="11343/06 - Lei de Drogas", artigo="ART 28: Posse para consumo", tipo_penal="CAPUT: Quem adquirir... para consumo pessoal",
            pena_imposta=pena(0), pena_total_processo="0a0m0d", data_infracao="01/01/2010", data_sentenca="01/06/2010", transito_mp="01/09/2010",
            transito_processo="01/09/2010")
c47 = crime(reincidente_comum="S")
L = next(x for x in rp.analisar(reg([c47, c28]), HOJE)["presc_linhas"] if x["proc_crim"] == P1)
_av = " | ".join(L["avisos"])
confere("pode ter por base a condenação pelo art. 28" in _av and "REsp 1.672.654" in _av and "única condenação anterior" in _av,
        "P47: aviso na linha do outro crime: %s" % _av)
L = next(x for x in rp.analisar(reg([crime(), c28]), HOJE)["presc_linhas"] if x["proc_crim"] == P1)
confere("pode ter por base" not in " | ".join(L["avisos"]), "P47: sem reincidência marcada, sem aviso")

# ---------------- P48: revogação do sursis pela data da decisão ----------------
c48 = crime(data_infracao="01/01/2015", data_denuncia="01/02/2015", data_sentenca="01/06/2015", transito_mp="01/09/2015", transito_processo="01/09/2015")
ch48 = rp.chave_ajuste(c48, {})
r48 = reg([c48], _presc_ajustes={ch48: {"valores": {"modalidade": "SURSIS", "audiencia_sursis": "01/10/2015", "revogacao_sursis": "01/03/2020"}}})
L = rp.analisar(r48, HOJE)["presc_linhas"][0]
confere("da data da decisão que revogou o sursis" in (L.get("ppe_saldo_rotulo") or "") and "trânsito" in (L.get("ppe_rev_sursis_hipotese") or ""),
        "P48: termo na decisão, trânsito a verificar: %s" % L.get("ppe_saldo_rotulo"))

# ---------------- P50: prisão em outro processo durante o livramento: sem detração ----------------
P3 = "0000303-33.2020.8.12.0001"
r50 = reg([crime(pena_imposta=pena(8), pena_total_processo="8a0m0d", transito_processo="01/09/2012")],
          [ev("01/10/2012", "PRISÃO DEFINITIVA", proc=P1), ev("01/01/2018", "LIVRAMENTO CONDICIONAL", tipo=INT),
           ev("01/03/2019", "PRISÃO PREVENTIVA", proc=P3), ev("01/09/2019", "ALVARÁ DE SOLTURA", tipo=INT)],
          [inc("LIVRAMENTO CONDICIONAL", "01/01/2018", "Livramento condicional")], pena_total="8a0m0d", pena_remanescente="1a0m0d")
its = ra._detracao_outro_processo(r50, r50["_crimes"], r50["_crimes"], r50["_eventos"])
confere(not any(i["tipo"] == "detracao-prisao-em-outro-processo" for i in its)
        and any(i["tipo"] == "detracao-prisao-em-outro-processo-no-livramento" and i["nivel"] == "verificar" and "Tema 1.367" in i["fundamento"] for i in its),
        "P50: %s" % [(i["nivel"], i["tipo"]) for i in its])

# ---------------- P57 / S8027: pena cumprida pela detração não lançada ----------------
c8 = crime(data_infracao="31/01/2019", data_denuncia="02/03/2019", data_sentenca="10/05/2019", transito_mp="01/07/2019",
           transito_processo="01/07/2019", processo_criminal="8808271-00.2020.8.12.0001")
r8 = reg([c8], [ev("01/02/2019", "PRISÃO EM FLAGRANTE", proc=c8["processo_criminal"]), ev("30/04/2019", "LIBERDADE PROVISÓRIA", tipo=INT),
                ev("01/08/2019", "PRISÃO DEFINITIVA", proc=c8["processo_criminal"]), ev("10/05/2020", "FUGA", tipo=INT)],
         [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "01/08/2019", "Fechado - Regime Inicial")],
         pena_total="1a0m0d", pena_cumprida="0a9m14d", pena_remanescente="0a2m21d", situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)")
L = rp.analisar(r8, HOJE)["presc_linhas"][0]
confere("aparente" not in L["ppe_status"] and L["ppe_cor"] == "amarelo" and "extinção pelo cumprimento" in L["ppe_status"],
        "S8027: fundamento no cumprimento, não na prescrição aparente: %s / %s" % (L["ppe_status"], L["ppe_cor"]))

# ---------------- P57 / S1010 e S1012: SV 56 no rótulo da situação ----------------
r = rs.situacao_execucao({}, [ev("08/02/2024", "PRISÃO DEFINITIVA", proc=P1), ev("01/04/2026", "PRISÃO DOMICILIAR COM MONITORAMENTO ELETRÔNICO", tipo=INT)],
                         [], [crime()], date(2026, 10, 5))
confere(r["situacao_cumprimento"].startswith("EM CUMPRIMENTO (SV 56") and "INTERROMPIDA" in r["situacao_eventos"],
        "S1010: rótulo com a ressalva, regras pelo SEEU: %s | %s" % (r["situacao_cumprimento"], r["situacao_eventos"]))
evs = [ev("03/03/2026", "PRISÃO DEFINITIVA", proc=P1), ev("03/03/2026", "INCOMPATIBILIDADE DE REGIME - AGUARDANDO VAGA", tipo=INT)]
evs[1]["_incompat_corta"] = True
r = rs.situacao_execucao({}, evs, [], [crime()], date(2026, 10, 5))
confere(r["situacao_cumprimento"].startswith("EM CUMPRIMENTO? (a verificar - SV 56"), "S1012: %s" % r["situacao_cumprimento"])
r = rs.situacao_execucao({}, [ev("08/02/2024", "PRISÃO DEFINITIVA", proc=P1), ev("01/04/2026", "FUGA", tipo=INT)], [], [crime()], date(2026, 10, 5))
confere(r["situacao_cumprimento"] == "PENA INTERROMPIDA (sem evento de reinício)", "SV 56 não alcança a fuga: %s" % r["situacao_cumprimento"])
confere(rv.rotulo_parada({"situacao_cumprimento": "EM CUMPRIMENTO (SV 56: x)", "situacao_eventos": "PENA INTERROMPIDA"}).startswith("Pena interrompida no SEEU (SV 56"),
        "S1010: rótulo da parada nas abas")

# ---------------- P57 / S1042: Responde PADIC não é conduta ruim ----------------
r = reg([crime(pena_imposta=pena(6))], [ev("07/03/2024", "PRISÃO DEFINITIVA", proc=P1)],
        [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "07/03/2024", "Fechado - Regime Inicial")], pena_total="6a0m0d")
m = rv.modelo(copy.deepcopy(r), {}, {"conduta": "RESPONDE PADIC", "eventos": []}, [])
confere(m["conduta_ruim"] is False and m["conduta_apurar"] is True, "S1042: %s / %s" % (m.get("conduta_ruim"), m.get("conduta_apurar")))
m = rv.modelo(copy.deepcopy(r), {}, {"conduta": "MÁ", "eventos": []}, [])
confere(m["conduta_ruim"] is True, "S1042: conduta má continua ruim")

if falhas:
    print("FALHOU (decisões dos pareceres - leitura e prazos):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: decisões dos pareceres, leitura e prazos (P01-P07, P45-P51, P57 S1xxx/S8xxx)")
