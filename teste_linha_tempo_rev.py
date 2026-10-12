"""Teste de regressão da revisão da linha do tempo do indulto (auditoria de 12/10/2026): fundamentação "a verificar" sem afirmar
requisito atendido (A1), linhas "?" da aba no checklist de 2024/2025 (A2), extenso sem somar dias (M1), falta citada sem corte
(M2), art. 13 na comutação de 2024/2025 (M3), art. 5º do Decreto 2022 (M4), § 2º, I e art. 10 da mulher com 60 anos ou mais
(M5), 2/3 do impeditivo para baixo (M8), decreto sem comutação (M9), pena já cumprida (M10) e os baixos (soltura, motivo
decisivo, processo repetido, redação dos decretos antigos, ícone da falta homologada, fuga impeditiva, "0 dias", pena extinta
depois do decreto). Rodar: python teste_linha_tempo_rev.py"""
import copy
import re
import sys
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs
import rspe_indulto_tl as tl
import rspe_view as rv
import rspe_decretos as rd

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


# ---------------------------------------------------------------- casos simulados (mesmo formato do RSPE lido)
def crime(fato, sent, tr, artigo="ART 155: Furto", tipo="CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel, Reclusão: 1 a 4 anos E Multa",
          pena="2 ano(s), 0 mês(es) e 0 dia(s)", lei="2848/40 - Código Penal", proc="0000001-00.2020.8.12.0001", vga="N", extinto="Não"):
    return {"processo_criminal": proc, "processo_situacao": "", "tipo_processo": "ACAO PENAL", "vara_condenacao": "1ª Vara Criminal", "data_denuncia": fato,
            "data_sentenca": sent, "transito_mp": tr, "transito_processo": tr, "pena_total_processo": "PENA ORIGINÁRIA", "regime_sentenca": "Fechado",
            "lei": lei, "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena, "data_infracao": fato, "vga": vga, "resultado_morte": "N",
            "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "fracao_progressao": "", "fracao_livramento": "",
            "extinto": extinto, "suspenso": "Não", "artigo_rspe": artigo, "extinto_rspe": extinto, "extincao_fonte": ""}


def ev(tipo, motivo, data):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": ""}


def preso(d):
    return ev("PRISÃO/INÍCIO DE CUMPRIMENTO", "PRISÃO DEFINITIVA", d)


def inc(tipo, compl, ddec, dref=None):
    return {"tipo": tipo, "motivo": "", "complemento": compl, "data": "", "data_decisao": ddec, "data_referencia": dref or ddec, "processos": "", "situacao": "CONCEDIDO"}


def caso(crimes, eventos, incidentes=(), sexo="M", nasc="01/01/1980", pena_total=None, extra=None):
    r = {"versao_leitura_rspe": 4, "tribunal": "TJMS", "comarca": "Campo Grande", "vara": "1ª VEP", "data_geracao_rspe": "05/10/2026",
         "processo_execucao": "9999999-99.2020.8.12.0001", "status_execucao": "ATIVO", "nome": "SIMULADO", "data_nascimento": nasc,
         "regime_atual": "Fechado - ATIVO", "_sexo": sexo, "_sexo_fonte": "ficha", "pena_total": pena_total or "", "pena_cumprida": "",
         "pena_remanescente": "", "total_interrupcoes": "", "saldo_remidos": "", "execucao_extinta": "",
         "_crimes": copy.deepcopy(list(crimes)), "_eventos": copy.deepcopy(list(eventos)), "_incidentes": copy.deepcopy(list(incidentes))}
    if extra:
        r.update(extra)
    rs.reprocessar(r)
    return r


def linha(r):
    return rv.json_seguro(tl.linha(r, rv.HOJE))


def card(t, ano):
    return next((d for d in t["decretos"] if d["id"] == ano), None)


def textos(B):
    return [p["texto"] for p in B.get("peticao") or []]


C4 = crime("01/06/2022", "01/10/2022", "01/11/2022", pena="4 ano(s), 0 mês(es) e 0 dia(s)")

# A1 + B1: solto (liberdade provisória) antes do decreto - "a verificar" sem hipótese atendida
t = linha(caso([C4], [preso("01/01/2023"), ev("INTERRUPÇÃO", "LIBERDADE PROVISÓRIA", "01/06/2025")], pena_total="4a0m0d"))
B = card(t, "2025")["indulto"]
P = textos(B)
ok(B["status"] == "verificar" and P and not any(re.search(r"requisitos objetivos .* estão atendidos", x) for x in P)
   and all("A conferir nos autos: cumprimento interrompido em 01/06/2025" in x and "Confirmados esses pontos" in x for x in P), "A1 (interrupção): %s" % P)
ok(all("art. 50" not in f["det"]["fundamento"] for f in t["faixas"] if f["tipo"] == "liberdade"), "B1 soltura citada como fuga: %s" % t["faixas"])
Pc = textos(card(t, "2025")["comutacao"])
ok(Pc and all("art. 13" in x and "A conferir nos autos" in x for x in Pc), "A1/M3 comutação a verificar: %s" % Pc)

# A1 (falta a verificar) e M9: decreto da base (2016) sem hipótese atendida, sem comutação e com crime doloso na janela
f16 = next(f for f in rd.fichas() if f["id"] == "2016")
cr = crime("01/06/2015", "01/10/2015", "01/11/2015", artigo="ART 157: Roubo", vga="S")
Cx = [{"id": "C1", "cor": "", "proc": cr["processo_criminal"], "tipificacao": "Art. 157, CP", "nome": "", "fato": "01/06/2015", "sentenca": "", "transito": "",
       "pena": "4a0m0d", "pena_dias": 1460, "natureza": "", "reinc": "", "selos": {}, "_c": cr, "alerta_tempo": "", "extinto": False}]
xm = {"id": "2016", "ref": "25/12/2016", "alc": None, "s": "ver", "beneficio": "", "ind_ver": False, "detalhe": {"pena": 6570, "cumprido": 477},
      "mot": "A VERIFICAR - sentença posterior ao trânsito em julgado no RSPE: dado incoerente - conferir as datas da sentença e do trânsito",
      "falta_ind": ["art. 121 § 2º CP com fato em 24/08/2016, durante a execução (crime doloso: falta grave se reconhecida - LEP, art. 52)"], "falta_firme": [],
      "hips": [{"tipo": "indulto", "dispositivo": "art. 3º, I", "ok": False, "exigido": None, "mot": "pena total de 18a0m0d acima de 12 anos"}]}
cum = lambda ref: {"total": 477, "cumprimento": 477, "detracao": 0, "remicao": 0, "perda": 0, "nao_comprovado": 0, "fonte": "", "eventos": 477, "diferenca": 0}
dd = tl._decreto_ficha(f16, xm, Cx, cum, [], None)
ok(dd["comutacao"]["status"] == "nao" and dd["comutacao"]["rotulo"] == "Decreto sem comutação" and not dd["comutacao"]["texto_aba"], "M9: %s" % dd["comutacao"])
ok(any(f["fato"] == "24/08/2016" and f["estado"] == "verificar" for f in dd["faltas"]), "A1 falta do motor fora da lista: %s" % dd["faltas"])
dd["alcance"] = tl._alcance(dd, Cx)
dd["_sexo"] = "M"
P = textos({"peticao": tl._peticao(dd, "indulto", {"C1": "art. 157 CP"})})
ok(P and "estão atendidos." not in P[0] and "não houve falta grave" not in P[0] and "sentença posterior ao trânsito" in P[0]
   and "a falta na janela de 23/12/2015 a 23/12/2016" in P[0], "A1 (2016): %s" % P)
R = tl._resumo(dd, "indulto")
ok(any(l.startswith("Falta grave de 23/12/2015 a 23/12/2016: 24/08/2016") and "sem homologação" in l for l in R)
   and not any("não houve falta grave" in l for l in R), "A1 resumo: %s" % R)

# A2: as linhas "?" do detalhe (§ 2º, XVI) entram no checklist; o § 2º vira enquadramento (art. 9º, § 2º, II a VI)
lin = tl._linhas_aba_tl("✘ Inciso XII: exige 1/5.\nObs.: § 2º, II a VI: com a metade do lapso, alcançaria os incisos IV - dados que o RSPE não traz: conferir.",
                        "? XVI: saúde/deficiência - não aferível pelo RSPE (laudo médico)\n? § 2º, II a VI: com a metade do lapso, alcançaria os incisos IV")
ok([e for e, _ in lin] == ["ko", "q", "q"] and lin[1][1].startswith("§ 2º") and lin[2][1].startswith("XVI"), "A2 linhas: %s" % lin)
ok(tl._hip_partes({"texto": lin[1][1]}, {"id": "2024"})[0] == "art. 9º, § 2º, II a VI", "A2 enquadramento do § 2º")

# M1: extenso pelo total de dias (1a11m30d = 725 dias, não 2 anos)
ok(tl._pena_ext("1a11m30d") == "1 ano, 11 meses e 30 dias" and tl._pena_ext("0a5m31d") == "6 meses e 1 dia", "M1: %s" % tl._pena_ext("1a11m30d"))
t = linha(caso([crime("01/06/2022", "01/10/2022", "01/11/2022")], [preso("01/01/2023")], pena_total="2a0m0d"))
P = textos(card(t, "2024")["indulto"])
ok(P and all("havia cumprido 1 ano, 11 meses e 30 dias" in x and "2 anos," not in x.split("Enquadra")[0] for x in P), "M1 petição: %s" % P[:1])

# M2 e B8/B2: falta homologada e fuga
c = tl._curto("INTERRUPÇÃO FUGA (fuga não homologada: tratada como falta grave, LEP, art. 50, II) e mais um texto longo qualquer aqui", 80)
ok("art. 50, I)" not in c and c.count("(") == c.count(")"), "M2 corte: %s" % c)
t = linha(caso([C4], [preso("01/01/2023"), ev("INTERRUPÇÃO", "FUGA", "01/03/2025"), ev("REINÍCIO", "RECAPTURA", "01/04/2025")], pena_total="4a0m0d"))
R = card(t, "2025")["indulto"]["resumo"]
ok(not any(re.search(r"art\. 50, I(?!I)", l) or l.count("(") != l.count(")") for l in R), "M2 resumo: %s" % R)
t = linha(caso([C4], [preso("01/01/2023")], [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "10/06/2025", "01/08/2025", "10/06/2025")], pena_total="4a0m0d"))
B = card(t, "2025")["indulto"]
ok(all(c_["estado"] == "ko" for c_ in B["checklist"] if c_["texto"].startswith("FALTA nos")), "B8 ícone: %s" % [c_ for c_ in B["checklist"] if c_["item"] == "Ressalva"])
ok(re.search(r"Não cabe o indulto em 25/12/2025: Falta com sanção reconhecida", B["fundamentacao"] or ""), "B2 motivo decisivo: %s" % B["fundamentacao"])

# M3: comutação de 2024/2025 com o art. 13 (caput e § 1º, base no cumprido)
R157 = dict(artigo="ART 157: Roubo", tipo="CAPUT: Subtrair coisa móvel alheia, para si ou para outrem, mediante grave ameaça ou violência a pessoa, Reclusão: 4 a 10 anos", vga="S")
t = linha(caso([crime("01/06/2021", "01/10/2021", "01/11/2021", pena="6 ano(s), 0 mês(es) e 0 dia(s)", **R157)], [preso("01/01/2022")], pena_total="6a0m0d"))
B = card(t, "2025")["comutacao"]
P = textos(B)
ok(B["status"] == "cabe" and P and P[0].count("Enquadra-se no art. 13, caput, e § 1º, do Decreto nº 12.790/2025") == 1
   and "(Decreto nº 12.790/2025, art. 13; LEP, art. 192)" in P[0] and B["peticao"][0]["rotulo"] == "art. 13, caput, e § 1º", "M3: %s" % P)

# M4: Decreto 2022 com o art. 5º
t = linha(caso([crime("01/03/2020", "01/08/2020", "01/09/2020")], [preso("01/01/2021")], pena_total="2a0m0d"))
P = textos(card(t, "2022")["indulto"])
ok(P and "Enquadra-se no art. 5º, caput e parágrafo único, do Decreto nº 11.302/2022" in P[0] and "art. 155 CP - pena máxima cominada de 4 anos" in P[0], "M4: %s" % P)

# M5: mulher com 65 anos - § 2º, I citado com exigido x cumprido, e o art. 10 entre os enquadramentos
t = linha(caso([crime("01/06/2023", "01/10/2023", "01/11/2023", pena="10 ano(s), 0 mês(es) e 0 dia(s)", tipo="§ 4º: Furto qualificado, Reclusão: 2 a 8 anos E Multa")],
               [preso("01/01/2024")], sexo="F", nasc="01/01/1960", pena_total="10a0m0d"))
B = card(t, "2025")["indulto"]
rot = [p["rotulo"] for p in B["peticao"]]
p2 = next((p["texto"] for p in B["peticao"] if p["rotulo"] == "art. 9º, II"), "")
ok("art. 10, III, c" in rot and "½" not in p2 and "art. 9º, § 2º, I" in p2 and "exigidos 1 ano, 8 meses e 3 dias" in p2, "M5: %s | %s" % (rot, p2))

# M8: 2/3 do impeditivo arredondados para baixo (5.110 dias -> 3.406)
ok(rs._dois_tercos(5110) == 3406, "M8: %s" % rs._dois_tercos(5110))

# M10: pena considerada já cumprida - pede a extinção pelo cumprimento, não o indulto
d10 = {"id": "2025", "numero": "12.790/2025", "referencia": "25/12/2025", "cumprido_txt": {"total": "0a3m26d"}, "alcance": {"crimes": [{"id": "C1", "crime": "Art. 155, CP", "proc": "1"}], "fora": []},
       "indulto": {"status": "cabe", "rotulo": "Possível · III", "pena_considerada_txt": "0a1m18d", "cumprido_txt": "0a3m26d", "checklist": [
           {"item": "Requisito objetivo / hipótese", "estado": "ok", "texto": "Inciso III: pena ≤ 4 anos com VGA, exige 1/3 (cumprido 0a3m26d de 0a1m18d)."}]}}
P = tl._peticao(d10, "indulto", {"C1": "art. 155 CP"})
ok(len(P) == 1 and P[0]["rotulo"] == "pena já cumprida (extinção)" and "concessão do indulto" not in P[0]["texto"] and "extinção da pena pelo integral cumprimento" in P[0]["texto"], "M10: %s" % P)
ok(any(l.startswith("Pena já cumprida") for l in tl._resumo(d10, "indulto")), "M10 resumo")

# B3: o nome já com a ação penal não repete o processo
d3 = dict(d10, indulto=dict(d10["indulto"], pena_considerada_txt="2a0m0d"), alcance={"crimes": [{"id": "C1", "crime": "x", "proc": "0000001-00.2020.8.12.0001"}], "fora": []})
P = tl._peticao(d3, "indulto", {"C1": "art. 155 CP (ação penal 0000001-00.2020.8.12.0001)"})
ok(P and "(processo 0000001-00.2020.8.12.0001)" not in P[0]["texto"], "B3: %s" % P)

# B4: redação dos decretos antigos
ok(tl._cond_prosa("crime patrimonial sem VGA, 3 meses cumpridos")[0] == "crime patrimonial sem violência ou grave ameaça, 3 meses cumpridos", "B4 patrimonial")
ok(tl._cond_prosa("Nos crimes praticados sem grave ameaça (Vide ADIN 5874)")[0] == "nos crimes praticados sem grave ameaça", "B4 maiúscula/ADIN: %s" % (tl._cond_prosa("Nos crimes praticados sem grave ameaça (Vide ADIN 5874)"),))
d4 = dict(d3, id="2003", numero="4.904", indulto=dict(d3["indulto"], checklist=[{"item": "Requisito objetivo / hipótese", "estado": "ok", "det": {
    "evento": "condenado à pena privativa de liberdade não superior a seis anos que tenha cumprido um terço da pena"},
    "texto": "art. 2º: atendida - cumpridos 1a0m0d em 25/12/2003 (exigido 0a8m0d, 1/3)"}]))
P = tl._peticao(d4, "indulto", {"C1": "art. 155 CP"})
ok(P and "Enquadra-se no art. 2º do Decreto nº 4.904/2003, que alcança o condenado à pena" in P[0]["texto"], "B4 art. 2º/concordância: %s" % P)

# B9: a evasão lida da ficha (regressão cautelar) e a fuga do evento são a mesma falta, impeditiva; homologação antes do fato
r = caso([C4], [preso("01/01/2023"), ev("INTERRUPÇÃO", "FUGA", "22/05/2025"), ev("REINÍCIO", "RECAPTURA", "01/06/2025")],
         [inc("FIXAÇÃO/ALTERAÇÃO DE REGIME", "Fechado - Regressão Cautelar", "04/09/2025"), inc("HOMOLOGAÇÃO DE FALTA GRAVE", "28/09/2025", "19/02/2025", "28/09/2025")],
         pena_total="4a0m0d")
r["_incidentes"][0]["_ficha_falta"] = {"data": "22/05/2025", "texto": "Saída da Unidade Penal: X, Destino: EVASÃO, Motivo: Evasão", "homologada": ""}
t = linha(r)
fl = card(t, "2025")["faltas"]
ok(any(f["fato"] == "22/05/2025" and f["estado"] == "impede" for f in fl) and not any(f["estado"] == "verificar" for f in fl), "B9 fuga: %s" % fl)
ok(any("antes do fato" in d["texto"] for d in t["duvidas"]), "B9 homologação antes do fato: %s" % t["duvidas"])

# "0 dias": o resumo não soma parcelas zeradas
ok(not any(re.search(r"\b0 dias", l) for l in card(linha(caso([C4], [preso("01/01/2023")], pena_total="4a0m0d")), "2024")["indulto"]["resumo"]), "0 dias no resumo")

# B11: pena em execução na data do decreto e extinta 5 dias depois - não "sem crimes ativos"
cx = crime("01/06/2020", "01/10/2020", "01/11/2020", extinto="Sim")
cx["data_extincao"] = "30/12/2022"
t = linha(caso([cx], [preso("01/01/2021"), ev("INTERRUPÇÃO", "EXTINÇÃO DA PENA", "30/12/2022")], [inc("EXTINÇÃO DA PUNIBILIDADE", "CUMPRIMENTO DA PENA", "30/12/2022")],
               pena_total="2a0m0d", extra={"status_execucao": "EXTINTO", "execucao_extinta": "Sim"}))
B = card(t, "2022")["indulto"]
ok(B["status"] == "nao" and "em execução em 25/12/2022" in B["rotulo"] and "sem crimes ativos" not in (B.get("texto_aba") or ""), "B11: %s / %s" % (B["rotulo"], B.get("texto_aba")))

if falhas:
    print("FALHOU (linha do tempo - revisão 12/10):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: linha do tempo - revisão 12/10 (a verificar sem requisito atendido, linhas ? da aba, extenso sem somar dias, falta sem corte, art. 13, "
      "art. 5º de 2022, § 2º, I e art. 10, 2/3 para baixo, decreto sem comutação, pena já cumprida, soltura, motivo decisivo, processo repetido, "
      "decretos antigos, falta homologada, fuga impeditiva, 0 dias, pena extinta depois do decreto)")
