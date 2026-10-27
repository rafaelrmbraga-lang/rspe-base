"""Teste da correção 7.14.8 (base simulada independente), frente indulto e comutação: soltura pelo cumprimento da pena não é fuga
e orienta a extinção (LEP, art. 66, II); âncora do SEEU abaixo dos eventos com os dois resultados "a verificar" (vale o dos
eventos, que cita o inciso); remição pendente apontada também no "a verificar"; Decreto 4.495/2002 (falta nos 12 meses do art.
3º, I, barra também a comutação do crime violento); livramento em curso na hipótese "regime aberto ou livramento"; piso de 18
meses das hipóteses patrimoniais de pequeno valor; Decreto 8.940/2016, art. 9º, p. ú. (fuga não apurada: a verificar); Dia das
Mães 2017/2018 (tráfico comum: vedação legal alcança a comutação). Casos hipotéticos (base simulada), nomes fictícios.
Rodar: python teste_cob_indulto.py"""
import json
import os
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_ficha as rf
import rspe_scraper as rs

AQUI = os.path.dirname(os.path.abspath(__file__))
COB = os.path.join(AQUI, "casos_simulados", "cobertura")
HOJE = date(2026, 10, 12)
falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def caso(area, cid):
    return next(c for c in json.load(open(os.path.join(COB, area + ".json"), encoding="utf-8")) if c["id"] == cid)["rspe"]


def dec(r, did):
    return next(x for x in rd.avaliar(r, HOJE)["decretos"] if str(x["id"]) == did)


def analise(r):
    return rs.analise_decretos(r, r["_crimes"], r["_eventos"], r["_incidentes"], HOJE)


# 1. (S6058) soltura por "CUMPRIMENTO DA PENA" antes do decreto: sem pena a indultar - pedir a extinção; não é fuga, e em 2025
# fica fora da janela do art. 6º
o = analise(caso("indulto_novos", "S6058"))
ok((o.get("indulto_2024") or "").startswith("não se aplica: sem pena remanescente") and "extinção pelo cumprimento" in o.get("indulto_2024"),
   "S6058: 2024 deve orientar a extinção: %s" % o.get("indulto_2024"))
for a in ("2024", "2025"):
    ok("falta a verificar" not in (o.get("indulto_" + a) or ""), "S6058: soltura por cumprimento não é falta (%s): %s" % (a, o.get("indulto_" + a)))
ok(rs.RE_SOLTURA_CUMPRIMENTO.search("CUMPRIMENTO DA PENA") and not rs.RE_SOLTURA_CUMPRIMENTO.search("INTERRUPCAO DO CUMPRIMENTO DA PENA"),
   "S6058: o motivo genérico 'interrupção do cumprimento' não é soltura por cumprimento")

# 2. (S6072) SEEU 400 dias abaixo dos eventos: o indulto a verificar cita o inciso I (atendido pelos eventos), como a comutação
o = analise(caso("indulto_novos", "S6072"))
t = (o.get("indulto_2024") or "").split(" | ")[0]
ok(t.startswith("A VERIFICAR") and " I," in t + ",", "S6072: o indulto deve citar o inciso I: %s" % o.get("indulto_2024"))
ok(rs._incisos_verif("A VERIFICAR: art. 9º, § 2º, II a VI (metade do lapso)") == set(), "S6072: § 2º não conta como inciso atendido")

# 3. (S5049) remição pendente que cobre o que faltava: apontada também quando o resultado já é "a verificar" por outro motivo
r = dict(caso("remicao", "S5049"))
r.update(analise(r))
ok((r.get("indulto_2024") or "").startswith("A VERIFICAR"), "S5049: premissa - indulto 2024 a verificar: %s" % r.get("indulto_2024"))
comp = {"fd_novo": {"fatos": [{"data": date(2024, 11, 30), "rotulo": "Atestado de trabalho nº 120/2024 (70 dias)", "dias": 70}]}}
rf.remicao_pendente_decretos(r, comp)
ok((r.get("indulto_2024") or "").startswith("A VERIFICAR (remição pendente)") and "também a verificar" in r["indulto_2024"]
   and "24 dias" in r["indulto_2024"], "S5049: remição pendente no 'a verificar': %s" % r.get("indulto_2024"))

# 4. (S7006) Decreto 4.495/2002, roubo com falta homologada nos 12 meses: o art. 3º, I, barra indulto e comutação
x = dec(caso("decretos_antigos", "S7006"), "2002")
ok(x["s"] == "nao" and "falta grave" in (x.get("mot") or "") and "12 meses" in x["mot"], "S7006: 2002 não cabe pela falta: %s | %s" % (x["s"], x.get("mot")))
x = dec(caso("decretos_antigos", "S7006"), "2003")
ok(x["s"] == "nao" and "falta grave" in (x.get("mot") or ""), "S7006: 2003 não cabe pela falta: %s | %s" % (x["s"], x.get("mot")))

# 5. (S7024) Decreto 11.846/2023, art. 2º, XIV: em livramento condicional (última decisão de regime: semiaberto) - atendido
x = dec(caso("decretos_antigos", "S7024"), "2023")
ok(x["s"] == "cabe" and x.get("beneficio") == "Indulto" and x.get("dispositivo") == "art. 2º, XIV",
   "S7024: indulto pelo XIV em livramento: %s %s %s" % (x["s"], x.get("beneficio"), x.get("dispositivo")))

# 6. (S7027) Decreto 7.873/2012, art. 1º, XVI: pena de 1a2m não supera 18 meses - a hipótese não aparece como a verificar
x = dec(caso("decretos_antigos", "S7027"), "2012")
ok(x["s"] == "ver" and "XV" in (x.get("mot") or "") and "XVI" not in (x.get("mot") or ""), "S7027: só o XV a verificar: %s" % x.get("mot"))
ok(rd._anos_pena(1.5) == 545 and rd._anos_pena(8) == 2920, "piso de 18 meses = 1a6m0d (545 dias): %s" % rd._anos_pena(1.5))

# 7. (S7036) Decreto 8.940/2016, art. 9º, p. ú.: fuga na janela sem apuração - a declaração fica postergada (a verificar)
x = dec(caso("decretos_antigos", "S7036"), "2016")
ok(x["s"] == "ver" and "posterga" in (x.get("mot") or ""), "S7036: 2016 a verificar: %s | %s" % (x["s"], x.get("mot")))

# 8. (S7038) Dia das Mães 2017 e 2018, mulher, tráfico comum: a vedação legal alcança também a comutação
for did in ("2017_maes", "2018_maes"):
    x = dec(dict(caso("decretos_antigos", "S7038"), _sexo="F"), did)  # o sexo vem da ficha do SIAPEN
    ok(x["s"] == "imp" and "Lei 8.072/90" in (x.get("mot") or ""), "S7038: %s impeditivo: %s | %s" % (did, x["s"], x.get("mot")))

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f in falhas:
        print(" -", f)
    sys.exit(1)
print("ok: correção 7.14.8, indulto (soltura por cumprimento, âncora x eventos, remição pendente no a verificar, 2002 art. 3º, I, "
      "livramento no XIV, piso de 18 meses, 2016 art. 9º, p. ú., Dia das Mães e tráfico)")
