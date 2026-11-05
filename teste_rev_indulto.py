"""Teste da correção 7.15.2, frente indulto e comutação (revisões jurídicas dos caps. 6 e 7): prisão provisória pelo próprio
processo conta no requisito temporal (2024/2025, art. 5º; STJ, Tema 1277 - também nos decretos sem a cláusula), a verificar;
comutação de 2/3 do art. 13, § 4º, lembrada para o art. 9º, § 2º, II a VI; comutação não fica "prejudicada" depois que uma camada
rebaixa o indulto; janela de 12 meses do art. 6º com o dia do começo incluído; incisos VI e X (dia do começo; metade do § 2º no IX
e no X); nota do aberto inicial no VIII; sentença registrada depois do trânsito e condenação sem data de trânsito (2024/2025);
art. 4º de 2022 com 1/3 arredondado para baixo; sexo não informado na hipótese das mulheres; remição pendente que cobre só a
comutação; tráfico sem parágrafo na execução posterior ao decreto; decreto restrito com falta; tese das comutações anteriores;
"praticados após" (2016: a tese continua); petição com o tempo que decidiu; textos e citações (Tema 1195, Tema 1267, AgRg no HC 894.488, HC 1.089.923,
SV 63, art. 8º de 2022, AgRg no HC 1.042.931). Casos hipotéticos, nomes fictícios.
Rodar: python teste_rev_indulto.py"""
import json
import os
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_indulto_tl as tl
import rspe_scraper as rs

AQUI = os.path.dirname(os.path.abspath(__file__))
HOJE = date(2026, 11, 5)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P1 = "0000001-11.2015.8.12.0001"
P2 = "0000002-11.2020.8.12.0001"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
IN = "INTERRUPÇÃO"


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "§ 4º: Furto qualificado, Reclusão: 2 a 8 anos", "pena_imposta": "2 ano(s), 0 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "10/01/2024", "data_sentenca": "10/07/2024", "transito_mp": "20/08/2024",
         "transito_processo": "20/08/2024", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "regime_sentenca": "Aberto"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, procs=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def inc(tipo, compl, data, ref=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": compl, "data_decisao": data, "data_referencia": ref or data, "situacao": sit, "processos": ""}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, **kw):
    r = {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
         "data_geracao_rspe": "05/10/2026", "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": "M",
         "status_execucao": "ATIVO", "regime_atual": "Aberto - ATIVO", "_crimes": crimes, "_eventos": eventos,
         "_incidentes": incid or [], "total_interrupcoes": "", "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}
    r.update(kw)
    return r


def der(r):
    rs.derivar(r, r["_crimes"], r["_eventos"], r["_incidentes"])
    return r


def dec(r, ano, completo=False):
    return next(x for x in rd.avaliar(r, HOJE, completo)["decretos"] if str(x["id"]) == ano)


ARMA = dict(lei="10826/03 - Estatuto do Desarmamento", artigo="ART 14: Porte ilegal de arma de fogo de uso permitido",
            tipo_penal="CAPUT: Portar, Reclusão: 2 a 4 anos")
ROUBO = dict(artigo="ART 157: Roubo", tipo_penal="CAPUT: Subtrair coisa móvel, Reclusão: 4 a 10 anos", vga="S")

# 1. (cap. 6, achado 1) furto de 2 anos, flagrante de 183 dias, solto antes do trânsito: 2024/2025 contam a prisão provisória
#    (art. 5º; STJ, Tema 1277) - A VERIFICAR com o inciso I e a comutação, nunca "não iniciou o cumprimento"
ev1 = [ev(PR, "PRISÃO EM FLAGRANTE", "10/01/2024"), ev(IN, "LIBERDADE PROVISÓRIA", "10/07/2024")]
r1 = der(reg([crime()], ev1, "2a0m0d", "0a6m3d"))
for a in ("2024", "2025"):
    t, tc = r1.get("indulto_" + a) or "", r1.get("comutacao_" + a) or ""
    ok(t.startswith("A VERIFICAR: art. 9º, I,") and "Tema 1277" in t and "não iniciou" not in t, "1: indulto %s: %s" % (a, t))
    ok(tc.startswith("A VERIFICAR: art. 13") and "não iniciou" not in tc, "1: comutação %s: %s" % (a, tc))
ok("2.257.552" in (r1.get("indulto_2024_detalhe") or ""), "1: a corrente contrária da 5ª Turma no detalhamento")
# 1b. regime aberto fixado, sem início registrado, com prisão provisória anterior: idem; o VII (regime) fica a verificar
r1b = der(reg([crime()], ev1, "2a0m0d", "0a6m3d", [inc("Fixação de regime", "ABERTO", "01/09/2024")]))
t = r1b.get("indulto_2024") or ""
ok(t.startswith("A VERIFICAR") and "Tema 1277" in t and "não iniciou" not in t, "1b: %s" % t)
ok("? VII:" in (r1b.get("indulto_2024_detalhe") or "") and "o cumprimento no regime não começou" in (r1b.get("indulto_2024_detalhe") or ""),
   "1b: VII a verificar: %s" % r1b.get("indulto_2024_detalhe"))
# 1c. (cap. 7, achado A1) decreto sem a cláusula da detração (2016): a prisão provisória conta pelo Tema 1277, a verificar; o de 2015
#     (com a cláusula) segue a conta
c1c = crime(data_infracao="10/03/2014", data_sentenca="10/06/2015", transito_mp="20/10/2015", transito_processo="20/10/2015",
            pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)")
r1c = reg([c1c], [ev(PR, "PRISÃO EM FLAGRANTE", "10/03/2014"), ev(IN, "LIBERDADE PROVISÓRIA", "09/09/2015")], "4a0m0d", "1a6m0d")
x = dec(r1c, "2016")
ok(x["s"] == "ver" and "Tema 1277" in (x.get("ressalva") or "") and "não iniciou" not in (x.get("mot") or ""), "1c: 2016 %s" % x)
x = dec(r1c, "2015")
ok(x["s"] == "cabe" and "art. 4º" in (x.get("ressalva") or ""), "1c: 2015 %s" % x)

# 2. (cap. 6, achados 2 e 11) roubo de 6 anos (fora dos incisos I a III), comutação de 1/5 possível: nota do art. 13, § 4º (2/3)
c2 = crime(data_infracao="01/06/2023", data_sentenca="01/11/2023", transito_mp="01/12/2023", transito_processo="01/12/2023",
           pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", regime_sentenca="Fechado", **ROUBO)
r2 = der(reg([c2], [ev(PR, "PRISÃO DEFINITIVA", "01/01/2024")], "6a0m0d", "2a9m0d", regime_atual="Fechado - ATIVO"))
t = r2.get("comutacao_2025") or ""
ok(t.startswith("POSSÍVEL: art. 13 (1/5") and "art. 13, § 4º" in t, "2: comutação 2025: %s" % t)
ok("a comutação é de 2/3" in (r2.get("comutacao_2025_detalhe") or "") and "§ 3º" in (r2.get("comutacao_2025_detalhe") or ""),
   "2: detalhe do § 4º: %s" % r2.get("comutacao_2025_detalhe"))

# 3. (cap. 6, achado 2; cap. 7, T6) data de nascimento divergente rebaixa o indulto: a comutação volta ao próprio resultado
c3 = crime(data_infracao="01/06/2024", data_sentenca="20/07/2024", transito_mp="01/08/2024", transito_processo="01/08/2024",
           pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", regime_sentenca="Semiaberto", **ARMA)
r3 = der(reg([c3], [ev(PR, "PRISÃO DEFINITIVA", "01/08/2024")], "4a0m0d", "2a3m0d", regime_atual="Semiaberto - ATIVO",
             data_nascimento="01/01/1960", _nasc_alt="01/01/1980"))
ok((r3.get("indulto_2024") or "").startswith("A VERIFICAR: data de nascimento divergente"), "3: premissa: %s" % r3.get("indulto_2024"))
ok(not (r3.get("comutacao_2024") or "").startswith("prejudicada"), "3: comutação ainda prejudicada: %s" % r3.get("comutacao_2024"))

# 4. (cap. 6, achado 8) janela do art. 6º: 12 meses contados com o dia do começo - de 26/12/2024 a 25/12/2025 no Decreto 2025
for fato, impede in (("25/12/2024", False), ("26/12/2024", True)):
    r4 = der(reg([c3], [ev(PR, "PRISÃO DEFINITIVA", "01/08/2024")], "4a0m0d", "2a3m0d", [inc("HOMOLOGAÇÃO DE FALTA GRAVE", fato, "10/02/2025")],
                 regime_atual="Semiaberto - ATIVO"))
    t = r4.get("indulto_2025") or ""
    ok(t.startswith("NÃO CABE (art. 6º)") == impede, "4: falta de %s: %s" % (fato, t))

# 5. (cap. 6, achado 5) sentença registrada depois de um trânsito anterior à publicação: na soma pelo trânsito, a verificar
c5 = crime(data_infracao="10/01/2023", data_sentenca="10/01/2025", transito_mp="10/12/2024", transito_processo="10/12/2024", regime_sentenca="Fechado")
r5 = der(reg([c5], [ev(PR, "PRISÃO DEFINITIVA", "10/01/2024")], "2a0m0d", "2a0m0d", regime_atual="Fechado - ATIVO"))
t = r5.get("indulto_2024") or ""
ok(t.startswith("A VERIFICAR") and "dado incoerente" in t and "sem condenação" not in t, "5: %s" % t)

# 6. (cap. 6, achado 6) condenação sem nenhuma data de trânsito leva ao "não atinge" da comutação; sem ela, cabe: a verificar
c6a = crime(data_infracao="01/01/2024", data_sentenca="10/05/2024", transito_mp="01/06/2024", transito_processo="01/06/2024", regime_sentenca="Fechado")
c6b = crime(processo_criminal=P2, pena_imposta="6 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="01/02/2020", data_sentenca="10/05/2021",
            transito_mp="", transito_processo="", regime_sentenca="Fechado", **ROUBO)
r6 = der(reg([c6a, c6b], [ev(PR, "PRISÃO DEFINITIVA", "01/06/2024", P1 + ", " + P2)], "8a0m0d", "2a3m0d", regime_atual="Fechado - ATIVO"))
t = r6.get("comutacao_2024") or ""
ok(t.startswith("A VERIFICAR (condenação sem data de trânsito no RSPE)") and "não atinge" in t, "6: %s" % t)

# 7. (cap. 6, achado 7; cap. 7, B2) 2022, art. 4º: 1/3 da pena em dias arredondado para baixo (pena de 3a0m1d = 1.096 dias: 365)
c7 = crime(data_infracao="01/01/2021", data_sentenca="01/06/2021", transito_mp="01/07/2021", transito_processo="01/07/2021",
           pena_imposta="3 ano(s), 0 mês(es) e 1 dia(s)", regime_sentenca="Fechado")
o7 = rs.analise_decreto_2022({"pena_total": "3a0m1d", "data_nascimento": "01/01/1940", "pena_cumprida": ""}, [c7],
                             [ev(PR, "PRISÃO DEFINITIVA", "26/12/2021")], [])
d7 = o7.get("indulto_2022_detalhe") or ""
ok("✓ art. 4º: 82 anos em 25/12/2022 e 1/3 cumprido (1a0m0d de 3a0m1d)" in d7, "7: 365 de 1.096 dias atendem o 1/3: %s" % d7)

# 8. (cap. 6, achado 9) inciso VI: 10 anos no semiaberto contados com o dia do começo (26/12/2014 a 25/12/2024 = 3.653 dias)
c8 = crime(data_infracao="01/01/2009", data_sentenca="01/06/2009", transito_mp="01/07/2009", transito_processo="01/07/2009",
           pena_imposta="20 ano(s), 0 mês(es) e 0 dia(s)", regime_sentenca="Fechado", **ROUBO)
r8 = der(reg([c8], [ev(PR, "PRISÃO DEFINITIVA", "01/07/2009")], "20a0m0d", "", [inc("PROGRESSÃO DE REGIME", "SEMIABERTO", "26/12/2014")],
             regime_atual="Semiaberto - ATIVO"))
ok("✔ VI:" in (r8.get("indulto_2024_detalhe") or ""), "8: VI: %s" % r8.get("indulto_2024_detalhe"))

# 9. (cap. 6, achado 10) inciso X com 60 anos ou mais: 1 ano e 6 meses (metade do § 2º)
c9 = crime(data_infracao="01/01/2020", data_sentenca="01/06/2020", transito_mp="01/07/2020", transito_processo="01/07/2020",
           pena_imposta="9 ano(s), 0 mês(es) e 0 dia(s)", regime_sentenca="Fechado", **ROUBO)
r9 = der(reg([c9], [ev(PR, "PRISÃO DEFINITIVA", "01/07/2020")], "9a0m0d", "", [inc("PROGRESSÃO DE REGIME", "SEMIABERTO", "01/01/2023")],
             regime_atual="Semiaberto - ATIVO", data_nascimento="01/01/1960"))
ok("? X: semiaberto há mais de 1 ano e 6 meses" in (r9.get("indulto_2024_detalhe") or ""), "9: X: %s" % r9.get("indulto_2024_detalhe"))

# 10. (cap. 6, achado 13) VIII no regime aberto fixado na sentença: nota da 6ª Turma (AgRg no HC 1.060.635), sem mudar o resultado
c10 = crime(data_infracao="01/01/2023", data_sentenca="01/06/2023", transito_mp="01/07/2023", transito_processo="01/07/2023", **ARMA)
r10 = der(reg([c10], [ev(PR, "INÍCIO DO CUMPRIMENTO REGIME ABERTO", "01/08/2023")], "2a0m0d", "", regime_atual="Aberto - ATIVO"))
ok("1.060.635" in (r10.get("indulto_2024_detalhe") or ""), "10: VIII: %s" % r10.get("indulto_2024_detalhe"))

# 11. (cap. 7, M3) sexo não informado na hipótese só das mulheres (Decreto 9.246/2017, art. 1º, IV): a verificar, não "faltavam"
c11 = crime(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico ilícito de drogas", tipo_penal="§ 4º: Tráfico privilegiado, Reclusão: 5 a 15 anos",
            data_infracao="01/01/2016", data_sentenca="10/02/2017", transito_mp="01/03/2017", transito_processo="01/03/2017",
            pena_imposta="1 ano(s), 8 mês(es) e 0 dia(s)", regime_sentenca="Semiaberto")
for sx, st in (("", "ver"), ("F", "cabe"), ("M", "nao")):
    x = dec(reg([c11], [ev(PR, "PRISÃO DEFINITIVA", "08/08/2017")], "1a8m0d", "", regime_atual="Semiaberto - ATIVO", _sexo=sx), "2017")
    ok(x["s"] == st, "11: sexo %r: %s - %s" % (sx, x["s"], x.get("mot")))

# 12. (cap. 7, M4) remição pendente que cobre só o que faltava para a comutação: a verificar
c12 = crime(data_infracao="01/01/2013", data_sentenca="10/02/2014", transito_mp="01/03/2014", transito_processo="01/03/2014",
            pena_imposta="9 ano(s), 0 mês(es) e 0 dia(s)", regime_sentenca="Fechado", **ROUBO)
r12 = reg([c12], [ev(PR, "PRISÃO DEFINITIVA", "01/03/2014")], "9a0m0d", "", regime_atual="Fechado - ATIVO")
ok(dec(r12, "2015")["s"] == "nao", "12: premissa")
r12["_rem_pend"] = [("30/11/2015", "atestado de trabalho de 2015", 160)]
x = dec(r12, "2015")
ok(x["s"] == "ver" and "comutação" in (x.get("mot") or ""), "12: %s - %s" % (x["s"], x.get("mot")))

# 13. (cap. 7, M5) execução iniciada depois do decreto, tráfico sem caput nem § 4º no RSPE: não é "impeditivo" firme
c13 = crime(lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico ilícito de drogas", tipo_penal="", pena_imposta="1 ano(s), 8 mês(es) e 0 dia(s)",
            data_infracao="01/01/2015", data_sentenca="10/02/2016", transito_mp="01/03/2016", transito_processo="01/03/2016")
x = dec(reg([c13], [ev(PR, "PRISÃO DEFINITIVA", "04/11/2024")], "1a8m0d", ""), "2016")
ok(x["s"] == "fora" and "tráfico sem indicação" in (x.get("mot") or ""), "13: %s - %s" % (x["s"], x.get("mot")))

# 14. (cap. 7, T5) decreto restrito (2019) com falta grave: o motivo é o decreto restrito
c14 = crime(data_infracao="01/01/2018", data_sentenca="10/02/2018", transito_mp="01/03/2018", transito_processo="01/03/2018",
            pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", regime_sentenca="Fechado", **ARMA)
x = dec(reg([c14], [ev(PR, "PRISÃO DEFINITIVA", "01/03/2018")], "4a0m0d", "", [inc("HOMOLOGAÇÃO DE FALTA GRAVE", "10/06/2019", "10/08/2019")],
            regime_atual="Fechado - ATIVO"), "2019")
ok(x["s"] == "nao" and (x.get("mot") or "").startswith("decreto restrito"), "14: %s - %s" % (x["s"], x.get("mot")))

# 15. (cap. 7, T4) tese das comutações anteriores: não no decreto vedado; com o número do decreto anterior
fx = {str(f["id"]): f for f in rd.fichas()}
out = [{"id": "2014", "ano": 2014, "numero": "8.380", "ref": "25/12/2014", "s": "ver", "beneficio": ""},
       {"id": "2015", "ano": 2015, "numero": "8.615", "ref": "25/12/2015", "s": "imp"}]
rd._tese_comutacoes_anteriores(out, fx, {})
ok(not out[1].get("tese_com_ant"), "15: tese no decreto vedado: %s" % out[1].get("tese_com_ant"))
out[1]["s"] = "nao"
rd._tese_comutacoes_anteriores(out, fx, {})
ok("Decreto 8.380 (2014)" in (out[1].get("tese_com_ant") or ""), "15: número do decreto: %s" % out[1].get("tese_com_ant"))

# 16. (cap. 7, B1) "praticados após" (Decreto 8.940/2016): a hediondez superveniente continua como tese (não procede)
f16 = dict(fx["2016"])
x16 = {"s": "cabe", "ref": "25/12/2016", "mot": "cumpriu"}
c16 = crime(artigo="ART 121: Homicídio", tipo_penal="§ 2º: Homicídio qualificado, Reclusão: 12 a 30 anos", vga="S", data_infracao="01/01/1993",
            data_sentenca="01/06/1994", transito_mp="01/07/1994", transito_processo="01/07/1994", pena_imposta="12 ano(s), 0 mês(es) e 0 dia(s)")
r16 = {"_crimes": [c16]}
ok(rd._tese_hediondez(dict(f16, impeditivos=dict(f16["impeditivos"], texto="hediondos")), r16, x16).get("s") == "ver", "16: premissa (sem a ressalva)")
# (o plural do Decreto 8.940/2016 - "praticados após a publicação da Lei 8.072/1990" - não afasta a dúvida da lei posterior que tornou
#  o crime hediondo: a tese continua - o achado B1 não procede; caso S7034 da base simulada)
ok(rd._tese_hediondez(f16, r16, x16).get("s") == "ver" and "praticados após" in (f16.get("impeditivos") or {}).get("texto", ""), "16: plural")

# 17. (cap. 6, achado 4) petição: o tempo que decidiu o resultado, e não o total da exibição
dd = {"id": "2024", "numero": "12.338/2024", "referencia": "25/12/2024", "cumprido_txt": {"total": "0a8m26d"},
      "indulto": {"status": "cabe", "cumprido_txt": "1a10m1d", "pena_considerada_txt": "5a0m0d", "checklist": []},
      "alcance": {"crimes": [{"id": "C1", "crime": "art. 297 CP", "proc": P1}]}, "_sexo": "M"}
P = tl._peticao(dd, "indulto", {"C1": "art. 297 CP"})
ok(P and "havia cumprido 1 ano, 10 meses e 1 dia" in P[0]["texto"], "17: %s" % (P[0]["texto"][:400] if P else P))

# 18. textos e citações
ok("salvo inércia ou mora estatal" in rd.FUGA_APURAR, "18: Tema 1195 com a ressalva da mora estatal: %s" % rd.FUGA_APURAR)
ok("Tema 1267" in rs.REINC_ART5_2022 and "2.268.813" in rs.REINC_ART5_2022 and "art. 12" in rs.REINC_ART5_2022, "18: reincidente no art. 5º de 2022")
ok("decisão monocrática" in rs.NOTA_REM_PEND and "HC 1.089.923" in rs.NOTA_REM_PEND, "18: HC 1.089.923")
ok("inciso VII" in rs.TXT_PROV_ART5 and "Tema 1277" in rs.TXT_PROV_ART5, "18: art. 5º")
o18 = {"indulto_2022": "POSSÍVEL: art. 5º", "indulto_2022_status": "possivel"}
rs._penas_a_verificar(o18, [crime(data_infracao="01/01/2021", suspenso="Sim")], "2022", date(2022, 12, 25))
ok("art. 8º, I" in (o18.get("indulto_2022") or "") and "sursis" in (o18.get("indulto_2022") or ""), "18: 2022, suspenso: %s" % o18.get("indulto_2022"))
c18 = crime(data_infracao="01/01/2024", data_sentenca="10/01/2025", transito_mp="10/02/2025", transito_processo="10/02/2025")
o18 = rs.analise_decretos(reg([c18], [ev(PR, "PRISÃO DEFINITIVA", "10/02/2025")], "2a0m0d", ""), [c18], [ev(PR, "PRISÃO DEFINITIVA", "10/02/2025")], [], HOJE)
ok("894.488" in (o18.get("indulto_2024_detalhe") or "") and "441.551" not in (o18.get("indulto_2024_detalhe") or ""),
   "18: sentença posterior: %s" % o18.get("indulto_2024_detalhe"))
ok("Súmula Vinculante 63" in (r2.get("indulto_2025_detalhe") or ""), "18: SV 63")
ok("nenhuma custódia" in (r1.get("indulto_2024_detalhe") or "") or "AgRg no HC 1.042.931" in (r1.get("indulto_2024_detalhe") or ""), "18: XV")
ok("inciso VIII, que depende de fração" not in json.dumps(r1, ensure_ascii=False, default=str), "18: texto antigo do VIII")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("OK - teste_rev_indulto")
