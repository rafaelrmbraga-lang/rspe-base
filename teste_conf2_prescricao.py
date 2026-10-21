"""Teste de regressão: conferência manual 7.14 (segunda rodada), frente "prescrição". Casos sintéticos, sem dados reais.
1. lista "Processos Selecionados" do evento terminada em vírgula (cortada na margem pelo SEEU): os processos impressos ligam a prisão
   (não vira "sem processo indicado"); a ação fora da lista impressa fica suspensa até o somatório que a inclui, com a nota da lista
   cortada; registro lido pela 7.13/7.14 (lista esvaziada) volta a lista impressa sem reimportar.
2. tese de saldo zero na fuga (critérios de imputação) também na aba Extinção; não sai quando condenação sem trânsito, por fato
   anterior à fuga, pode ter recebido o tempo antes.
3. "Suspenso: Sim" em crime que não admite a suspensão condicional do processo (pena mínima acima de 1 ano): aviso do ANPP/sursis.
4. intervalo sentença -> trânsito maior que o prazo: recurso ou demora na intimação.
5. reincidência sem base: o +1/3 sai também quando as outras condenações do RSPE ainda não transitaram.
Rodar: python teste_conf2_prescricao.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs  # noqa: E402
import rspe_prescricao as rp  # noqa: E402
import rspe_view as rv  # noqa: E402

HOJE = date(2026, 10, 20)
falhas = []
FURTO = "CAPUT: Subtrair, para si ou para outrem, coisa alheia móvel., Reclusão: 1 a 4 anos E Multa"
P1, P2, P3, P4 = "0000101-11.2018.8.12.0001", "0000202-22.2019.8.12.0001", "0000303-33.2020.8.12.0001", "0000404-44.2021.8.12.0001"
UM, DOIS, TRES = "1 ano(s), 0 mês(es) e 0 dia(s)", "2 ano(s), 0 mês(es) e 0 dia(s)", "3 ano(s), 0 mês(es) e 0 dia(s)"


def confere(cond, msg):
    if not cond:
        falhas.append(msg)


def crime(fato, tr, pena, proc=P1, artigo="ART 155: Furto", tipo=FURTO, den="", sent="", **kw):
    c = {"processo_criminal": proc, "data_infracao": fato, "data_denuncia": den, "data_sentenca": sent, "transito_mp": tr,
         "transito_processo": tr, "lei": "2848/40 - Código Penal", "artigo": artigo, "tipo_penal": tipo, "pena_imposta": pena,
         "pena_total_processo": "%s - PENA ORIGINÁRIA" % pena, "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não"}
    c.update(kw)
    return c


def ev(data, motivo, tipo="PRISÃO/INÍCIO DE CUMPRIMENTO", proc="", **kw):
    e = {"tipo": tipo, "motivo": motivo, "data": data, "processos": proc}
    e.update(kw)
    return e


def reg(crimes, eventos=(), incidentes=(), **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": "01/01/1980",
         "data_geracao_rspe": "06/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO"}
    r.update(kw)
    return r


def linha(r, proc):
    return next(l for l in rp.analisar(r, HOJE)["presc_linhas"] if l["proc_crim"] == proc)


# ---------------- 1. lista do evento terminada em vírgula ----------------
BLOCO = "Tipo: PRISÃO/INÍCIO DE CUMPRIMENTO\nMotivo: PRISÃO PREVENTIVA\nData: 10/01/2023\nProcessos Selecionados: %s, %s, %s,\n" % (P1, P2, P3)
b = rs.blocos_tipo(BLOCO)[0]
confere(b.get("processos_incompletos"), "1: lista com vírgula final marcada como cortada")
evs = [dict(b)]
rs._completar_processos_eventos([crime("01/01/2018", "01/01/2020", UM, proc=P1)], evs, [])
confere(all(p in evs[0]["processos"] for p in (P1, P2, P3)), "1: os processos impressos ligam a prisão: %s" % evs[0])
confere(evs[0]["processos_rspe"].startswith(P1), "1: lista impressa guardada para o aviso")
# registro lido pela 7.13/7.14: lista esvaziada, impressa em processos_rspe - volta sem reimportar
velho = [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO PREVENTIVA", "data": "10/01/2023", "processos": "",
          "processos_incompletos": True, "processos_rspe": "%s, %s," % (P1, P2)}]
rs._completar_processos_eventos([], velho, [])
confere(P1 in velho[0]["processos"] and P2 in velho[0]["processos"], "1: registro antigo recupera a lista impressa: %s" % velho[0])

# prisão preventiva em 10/01/2023 lançada em P1 (lista cortada); P4 (transitada em 2022, fora da lista impressa) só entra no
# somatório de 01/06/2024: até ele, a prescrição de P4 fica suspensa (preso por outro motivo), não é cumprimento desde a prisão
evc = ev("10/01/2023", "PRISÃO PREVENTIVA", proc=P1, processos_incompletos=True, processos_rspe="%s," % P1)
soma = {"tipo": "SOMATÓRIO DAS PENAS", "complemento": "", "data_referencia": "01/06/2024", "data_decisao": "01/06/2024",
        "situacao": "CONCEDIDO", "processos": "%s, %s" % (P1, P4)}
r = reg([crime("01/01/2022", "", TRES, proc=P1), crime("01/01/2019", "01/03/2022", UM, proc=P4)], [evc], [soma])
l = linha(r, P4)
lt = l["ppe_linha_tempo"]
confere(not any(x["tipo"] == "cumprimento" and x["inicio"] == "10/01/2023" for x in lt), "1: P4 não cumpre desde a prisão: %s" % lt)
confere(any(x["tipo"] == "cumprimento" and x["inicio"] == "01/06/2024" for x in lt), "1: P4 cumpre desde o somatório: %s" % lt)
confere(any("lista cortada no RSPE" in x["fonte"] for x in lt), "1: nota da lista cortada na prisão: %s" % lt)
confere(all("sem processo indicado" not in x["fonte"] for x in lt), "1: não aparece 'sem processo indicado'")

# ---------------- 2. tese de saldo zero na fuga, também na aba Extinção ----------------
# duas condenações (P1, 1 ano, trânsito 2018; P2, 8 anos, trânsito 2019), presas de 2017 a 2021 (fuga) - pela ordem do trânsito,
# P1 recebe o tempo primeiro e estava cumprida antes da fuga
cr = [crime("01/01/2017", "01/03/2018", UM, proc=P1), crime("01/02/2017", "01/03/2019", "8 ano(s), 0 mês(es) e 0 dia(s)", proc=P2)]
eventos = [ev("10/02/2017", "PRISÃO EM FLAGRANTE", proc="%s, %s" % (P1, P2)),
           ev("01/03/2021", "FUGA", tipo="INTERRUPÇÃO", proc="%s, %s" % (P1, P2)),
           ev("01/03/2026", "RECAPTURA", proc="%s, %s" % (P1, P2))]
pres = rp.analisar(reg(cr, eventos), HOJE)
l = next(x for x in pres["presc_linhas"] if x["proc_crim"] == P1)
confere(l.get("ppe_saldo_zero_crit"), "2: critério que zera o saldo registrado: %s" % l.get("ppe_saldo_zero_crit"))
ext = rv.extincao(reg(cr, eventos), pres, None)
confere(ext["ext_cor"] == "amarelo" and "ação penal %s): a verificar - pelo" % P1 in ext["ext_hipoteses"]
        and "já esgotava a pena deste crime (saldo zero)" in ext["ext_hipoteses"], "2: tese do saldo zero na aba Extinção: %s" % ext)
confere("ação penal %s): a verificar - pelo" % P2 not in ext["ext_hipoteses"], "2: sem a tese para a condenação com saldo: %s" % ext)
# condenação sem trânsito, por fato anterior à fuga, com pena que absorve o tempo: a tese não se sustenta
cr2 = cr + [crime("01/01/2016", "", "7 ano(s), 0 mês(es) e 0 dia(s)", proc=P3, artigo="ART 157: Roubo", tipo="CAPUT: Reclusão: 4 a 10 anos E Multa")]
l2 = linha(reg(cr2, eventos), P1)
confere(not l2.get("ppe_saldo_zero_crit") and "saldo seria zero" not in (l2.get("ppe_detalhe") or ""),
        "2: condenação sem trânsito anterior à fuga derruba a tese do saldo zero: %s" % l2.get("ppe_saldo_zero_crit"))

# ---------------- 3. "Suspenso: Sim" em furto qualificado (pena mínima de 2 anos) ----------------
QUALIF = "§ 4º: A pena é de reclusão de dois a oito anos, e multa, se o crime é cometido: I - com destruição"
confere(rs.pena_minima_abstrata({"tipo_penal": QUALIF}) is None and rs.pena_minima_abstrata({"tipo_penal": QUALIF}, extenso=True) == 2 * rs.DIAS_ANO,
        "3: pena mínima por extenso só com extenso=True")
l = linha(reg([crime("06/11/2015", "07/03/2022", DOIS, proc=P1, tipo=QUALIF, den="19/01/2017", sent="03/12/2021", suspenso="Sim")]), P1)
det = l.get("retro_detalhe") or ""
confere("não admite a suspensão condicional do processo" in det and "acordo de não persecução penal" in det,
        "3: aviso do ANPP/sursis no lugar do art. 89: %s" % det)
confere("art. 89, § 6º) não deixa correr" not in det, "3: sem o aviso da suspensão condicional do processo")
confere("conferir suspensão condicional do processo" not in l["retro_status"], "3: status sem a suspensão do processo: %s" % l["retro_status"])
# furto simples (mínima de 1 ano) continua com o aviso da suspensão do processo
l = linha(reg([crime("06/11/2015", "07/03/2022", UM, proc=P1, den="19/01/2017", sent="03/12/2021", suspenso="Sim")]), P1)
confere("suspensão condicional do processo (Lei 9.099/1995, art. 89, § 6º)" in (l.get("retro_detalhe") or ""), "3: furto simples mantém o aviso do art. 89")

# ---------------- 4. sentença -> trânsito maior que o prazo: recurso ou demora na intimação ----------------
l = linha(reg([crime("01/01/2018", "01/03/2024", DOIS, proc=P1, den="01/02/2018", sent="01/06/2019")]), P1)
det = l.get("retro_detalhe") or ""
confere("demora na" in det and "intimação" in det and "só se explica por recurso" not in det, "4: texto do recurso/intimação: %s" % det)

# ---------------- 5. reincidência sem base com a outra condenação sem trânsito ----------------
cr5 = [crime("06/01/2025", "16/03/2026", TRES, proc=P1, reincidente_comum="S"), crime("27/03/2025", "", TRES, proc=P2)]
l = linha(reg(cr5), P1)
confere(not l["reinc"] and "+1/3" not in (l.get("prazo_ppe") or ""), "5: +1/3 afastado com a outra condenação sem trânsito: %s" % l.get("prazo_ppe"))
# condenação única: segue a reincidência marcada (o RSPE não mostra o passado)
l = linha(reg(cr5[:1]), P1)
confere(l["reinc"], "5: condenação única mantém a reincidência marcada")

if falhas:
    print("FALHAS:\n- " + "\n- ".join(falhas))
    sys.exit(1)
print("ok: conferência 7.14, frente prescrição (lista cortada, saldo zero, ANPP/sursis, recurso/intimação, reincidência sem base)")
