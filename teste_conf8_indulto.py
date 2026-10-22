"""Teste da terceira conferência independente (7.14.7), frente indulto e comutação: decreto que manda computar a detração no
requisito temporal (2004-2015, art. 3º/4º; 2023, art. 5º) - a prisão provisória pelo próprio processo conta como pena cumprida, sem
"não iniciou o cumprimento"; decretos restritos (2019 a 2021: saúde e agentes de segurança) dão o motivo do decreto, não o "não
iniciou"; execução iniciada depois do decreto com condenação alcançada só por crime impeditivo = vedado (a mesma da coluna), também
no 2022 detalhado ("excluído (art. 7º)"); tráfico de fato posterior a todos os decretos aparece no rótulo "crime impeditivo".
Casos hipotéticos, nomes fictícios.
Rodar: python teste_conf8_indulto.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_scraper as rs
import rspe_view as rv

falhas = []
HOJE = date(2026, 10, 21)


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P1 = "0000001-11.2015.8.12.0001"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
IN = "INTERRUPÇÃO"


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "1 ano(s), 0 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "24/05/2023", "data_sentenca": "09/08/2023", "transito_mp": "20/09/2023",
         "transito_processo": "20/09/2023", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "regime_sentenca": "Aberto"}
    c.update(kw)
    return c


def ev(tipo, motivo, data, procs=P1):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": procs}


def reg(crimes, eventos, pena_total, cumprida="", **kw):
    r = {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
         "data_geracao_rspe": "05/10/2026", "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": "M",
         "status_execucao": "ATIVO", "regime_atual": "Aberto - ATIVO", "_crimes": crimes, "_eventos": eventos,
         "_incidentes": [], "total_interrupcoes": "", "saldo_remidos": "0 dias (0 dias remidos - 0 dias perdidos)"}
    r.update(kw)
    return r


def dec(r, ano, completo=False):
    return next(x for x in rd.avaliar(r, HOJE, completo)["decretos"] if str(x["id"]) == ano)


# 1. Decreto 11.846/2023, art. 5º: furto de 1 ano, prisão em flagrante convertida e solta na sentença (78 dias), sem início do
#    cumprimento em 25/12/2023 - a detração conta (1/5 = 73 dias): comutação cabível, com a nota do art. 5º; nunca "não iniciou"
ev1 = [ev(PR, "PRISÃO EM FLAGRANTE", "24/05/2023"), ev(IN, "LIBERDADE PROVISÓRIA", "09/08/2023")]
r1 = reg([crime()], ev1, "1a0m0d", "0a2m17d")
x1 = dec(r1, "2023")
ok("não iniciou" not in (x1.get("mot") or ""), "1: %s - %s" % (x1["s"], x1.get("mot")))
ok(x1["s"] in ("cabe", "ver") and "art. 5º" in (x1.get("ressalva") or "") + (x1.get("mot") or ""), "1: %s - %s / %s" % (
    x1["s"], x1.get("mot"), x1.get("ressalva")))

# 2. A mesma situação em 2015 (Decreto 8.615, art. 4º: detração computada) e o decreto de 2016 (sem a cláusula): em 2016, sem
#    início do cumprimento, segue "não iniciou"
c2 = crime(data_infracao="10/03/2015", data_sentenca="10/06/2015", transito_mp="20/07/2015", transito_processo="20/07/2015")
ev2 = [ev(PR, "PRISÃO EM FLAGRANTE", "10/03/2015"), ev(IN, "LIBERDADE PROVISÓRIA", "10/06/2015")]
r2 = reg([c2], ev2, "1a0m0d", "0a3m0d")
x2 = dec(r2, "2015")
ok("não iniciou" not in (x2.get("mot") or "") and "art. 4º" in (x2.get("ressalva") or "") + (x2.get("mot") or ""),
   "2: 2015 %s - %s / %s" % (x2["s"], x2.get("mot"), x2.get("ressalva")))
x2b = dec(r2, "2016")
ok(x2b["s"] == "nao" and "não iniciou" in (x2b.get("mot") or ""), "2: 2016 %s - %s" % (x2b["s"], x2b.get("mot")))

# 3. Decretos restritos (2019 e 2020: saúde e agentes de segurança): a hipótese não exige o início do cumprimento - o motivo é
#    o do decreto
c3 = crime(data_infracao="24/03/2019", data_sentenca="12/11/2019", transito_mp="20/12/2019", transito_processo="20/12/2019",
           pena_imposta="2 ano(s), 8 mês(es) e 0 dia(s)")
r3 = reg([c3], [ev(PR, "PRISÃO EM FLAGRANTE", "24/03/2019"), ev(IN, "LIBERDADE PROVISÓRIA", "25/03/2019")], "2a8m0d", "0a0m2d")
for ano in ("2019", "2020"):
    x3 = dec(r3, ano)
    ok(x3["s"] == "nao" and (x3.get("mot") or "").startswith("decreto restrito"), "3: %s %s - %s" % (ano, x3["s"], x3.get("mot")))

# 4. Estupro de vulnerável (2014), sentença em 2016, execução iniciada em 2024: a tabela dá a vedação (como a coluna), não
#    "execução posterior ao decreto"; 2019-2021 (restritos) dizem o motivo do decreto e o impeditivo
c4 = crime(artigo="ART 217-A: Estupro de vulnerável", tipo_penal="CAPUT: Ter conjunção carnal, Reclusão: 8 a 15 anos",
           pena_imposta="9 ano(s), 0 mês(es) e 0 dia(s)", data_infracao="27/08/2014", data_sentenca="26/02/2016",
           transito_mp="10/03/2016", transito_processo="10/03/2016", regime_sentenca="Fechado")
r4 = reg([c4], [ev(PR, "PRISÃO DEFINITIVA", "04/11/2024")], "9a0m0d", "1a11m0d", regime_atual="Fechado - ATIVO")
for ano in ("2016", "2017", "2023"):
    x4 = dec(r4, ano)
    ok(x4["s"] == "imp" and "217-A" in (x4.get("mot") or ""), "4: %s %s - %s" % (ano, x4["s"], x4.get("mot")))
for ano in ("2019", "2021"):
    x4 = dec(r4, ano)
    ok(x4["s"] == "nao" and "impeditivo" in (x4.get("mot") or ""), "4: %s %s - %s" % (ano, x4["s"], x4.get("mot")))
# 4b. crime comum na mesma situação: segue "execução posterior" (fora)
r4b = reg([crime(data_infracao="27/08/2014", data_sentenca="26/02/2016", transito_mp="10/03/2016", transito_processo="10/03/2016")],
          [ev(PR, "PRISÃO DEFINITIVA", "04/11/2024")], "1a0m0d", "0a3m0d")
ok(dec(r4b, "2017")["s"] == "fora", "4b: %s" % dec(r4b, "2017"))
# 4c. 2022 detalhado com "excluído (art. 7º)": é vedação (a coluna diz "Vedado (art. 7º)")
rs.derivar(r4, r4["_crimes"], r4["_eventos"], r4["_incidentes"])
x4c = dec(r4, "2022")
ok(x4c["s"] == "imp", "4c: 2022 %s - %s (%s)" % (x4c["s"], x4c.get("mot"), r4.get("indulto_2022")))

# 5. Tráfico (art. 33, caput) de fato posterior a todos os decretos: o rótulo "crime impeditivo" o indica, com a ressalva; a cor
#    da linha não fica vermelha só por ele
c5 = crime(processo_criminal="0000005-11.2026.8.12.0001", lei="11343/06 - Lei de Drogas", artigo="ART 33: Tráfico ilícito de drogas",
           tipo_penal="CAPUT: Importar, exportar, Reclusão: 5 a 15 anos", pena_imposta="5 ano(s), 6 mês(es) e 0 dia(s)",
           data_infracao="22/01/2026", data_sentenca="10/06/2026", transito_mp="20/07/2026", transito_processo="20/07/2026",
           regime_sentenca="Fechado")
r5 = reg([c5], [ev(PR, "PRISÃO EM FLAGRANTE", "22/01/2026")], "5a6m0d", "0a8m0d", regime_atual="Fechado - ATIVO")
rs.derivar(r5, r5["_crimes"], r5["_eventos"], r5["_incidentes"])
t5 = rv.curto_impeditivo(r5)
ok(t5.startswith("Sim") and "fato posterior" in t5, "5: %s / %s" % (t5, r5.get("indulto_crime_impeditivo_detalhe")))
ok(rv.cor_indulto(r5) != "vermelho", "5: cor %s" % rv.cor_indulto(r5))

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("OK - teste_conf8_indulto")
