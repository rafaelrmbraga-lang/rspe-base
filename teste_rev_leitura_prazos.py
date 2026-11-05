"""Teste de regressão: correção 7.15.2, frente "leitura e prazos" (revisões jurídicas dos capítulos 1 - leitura e situação, 8 -
prescrição e 9 - extinção). Casos sintéticos, com nomes e números fictícios.
1. (cap. 8, 1; cap. 9, A2) art. 366 sem data de fim: a suspensão vai, no máximo, até a véspera da sentença e não entra no trecho
   sentença → trânsito; se a retomada decide o trecho denúncia → sentença, A VERIFICAR com a data-limite.
2. (cap. 8, 2) crime continuado: a prescrição que só aparece sem o acréscimo (STF, Súmula 497) fica A VERIFICAR.
3. (cap. 8, 5 e 6; cap. 9, A7 e A8) revogação do livramento não é "fuga"; saldo zero não "interrompe".
4. (cap. 8, 3a, 8, 9, 10, 11, 12) citações: HC 429.545 como posição contrária, Tema 438, Súmula 220, Súmula 527 só como reforço,
   Tema 506 no art. 28, ponto discutível do art. 113 por analogia.
5. (cap. 9, A1) saldo de 360 a 364 dias: 11 meses e 25 a 29 dias (fim do período de prova e Súmula 617).
6. (cap. 9, A3) término do SEEU alcançado depois de fuga sem reinício: a verificar, não "extinção cabível".
7. (cap. 9, A6) detração que cobre a pena de um processo com outras penas ativas: a verificar (execução unificada).
8. (cap. 9, A4, A5, A10) ressalva do art. 89 pela Súmula 617 e pelo Tema 1.367.
9. (cap. 1, A1) crime no período sem trânsito nem falta reconhecida não move a data-base calculada.
10. (cap. 1, A2) conduta readquirida pelo lapso cumprido depois da falta (LEP, art. 112, § 7º): a conferir, não "não atende".
11. (cap. 1, A8) data-base pela decisão de progressão sem data de referência: amarelo (Tema 1165).
12. (cap. 1, B1, B2, B3) textos: VGA e Temas 1336/1400, remição e art. 75, Súmula 533 na fuga.
Rodar: python teste_rev_leitura_prazos.py (sai com código 1 se algum caso falhar)."""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_scraper as rs  # noqa: E402
import rspe_prescricao as rp  # noqa: E402
import rspe_view as rv  # noqa: E402

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
    c = {"processo_criminal": P1, "data_infracao": "01/01/2012", "data_denuncia": "01/02/2012", "data_sentenca": "01/06/2019",
         "transito_mp": "01/09/2023", "transito_processo": "01/09/2023", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": FURTO, "pena_imposta": pena(1), "pena_total_processo": "%s - PENA ORIGINÁRIA" % pena(1),
         "reincidente_comum": "N", "reincidente_especifico": "N", "extinto": "Não", "fracao_progressao": "1/6 - Comum"}
    c.update(kw)
    return c


def ev(data, motivo, tipo=PRI, proc=""):
    return {"tipo": tipo, "motivo": motivo, "complemento": "", "data": data, "data_decisao": "", "data_referencia": "", "processos": proc}


def inc(tipo, data, comp="", ref=None, sit="CONCEDIDO"):
    return {"tipo": tipo, "complemento": comp, "data_decisao": data, "data_referencia": data if ref is None else ref, "situacao": sit,
            "processos": ""}


def reg(crimes, eventos=(), incidentes=(), aj=None, **kw):
    r = {"_crimes": list(crimes), "_eventos": list(eventos), "_incidentes": list(incidentes), "data_nascimento": "01/01/1980",
         "data_geracao_rspe": "01/10/2026", "situacao_cumprimento": "EM CUMPRIMENTO", "processo_execucao": "0009999-99.2011.8.12.0001"}
    if aj:
        r["_presc_ajustes"] = aj
    r.update(kw)
    return r


def linha(r):
    return rp.analisar(r, HOJE)["presc_linhas"][0]


# ---------------- 1. art. 366 sem data de fim ----------------
c = crime()
ch = rp.chave_ajuste(c, {})
L = linha(reg([c], aj={ch: {"valores": {"susp366_ini": "01/06/2012"}}}))
confere(not L["retro_status"].startswith("não configurada"), "1: com a suspensão sem fim, a intercorrente não pode sumir: %s" % L["retro_status"])
confere("ainda suspenso" not in L["retro_detalhe"], "1: '(ainda suspenso)' com sentença: %s" % L["retro_detalhe"])
confere("✘ sentença → trânsito: 01/06/2019 a 01/09/2023 = 4 anos e 3 meses (prazo 4 anos, vence 31/05/2023)" in L["retro_detalhe"],
        "1: o trecho depois da sentença não recebe dias suspensos: %s" % L["retro_detalhe"])
confere("terminou até 29/09/2015" in L["retro_detalhe"], "1: data-limite da retomada (denúncia → sentença): %s" % L["retro_detalhe"])
# sem intercorrente (trânsito logo depois da sentença): o resultado depende só do fim da suspensão - A VERIFICAR
c1b = crime(transito_mp="01/09/2019", transito_processo="01/09/2019")
ch1b = rp.chave_ajuste(c1b, {})
L = linha(reg([c1b], aj={ch1b: {"valores": {"susp366_ini": "01/06/2012"}}}))
confere(L["retro_status"].startswith("A VERIFICAR") and "366" in L["retro_status"] and L["retro_cor"] == "amarelo",
        "1b: a retomada decide a punitiva: %s / %s" % (L["retro_status"], L["retro_cor"]))
# com a data de fim informada, a conta é a dela
L = linha(reg([c1b], aj={ch1b: {"valores": {"susp366_ini": "01/06/2012", "susp366_fim": "31/05/2019"}}}))
confere(L["retro_status"].startswith("não configurada"), "1c: suspensão informada até a véspera da sentença: %s" % L["retro_status"])

# ---------------- 2. crime continuado (Súmula 497) ----------------
c2 = crime(data_infracao="01/01/2014", data_denuncia="01/02/2014", data_sentenca="01/03/2019", transito_mp="01/05/2019",
           transito_processo="01/05/2019", pena_imposta=pena(2, 4), tipo_penal=FURTO + " (ART. 71 - CRIME CONTINUADO)")
L = linha(reg([c2]))
# P45 (7.15.3): prescrita em todas as frações do acréscimo - vermelho, não mais "A VERIFICAR" (teste ajustado à decisão do parecer)
confere("Súmula 497" in L["retro_status"] and L["retro_cor"] == "vermelho",
        "2: punitiva sem o acréscimo da continuidade: %s" % L["retro_status"])
confere("em qualquer fração" in L["retro_status"], "2: de 1/6 a 2/3 o prazo é de 4 anos - todas prescritas: %s" % L["retro_status"])
confere("Súmula 497" in L["ppe_status"] and L["ppe_cor"] == "vermelho", "2: executória sem o acréscimo: %s" % L["ppe_status"])
# sem continuidade, a mesma pena não prescreve
L = linha(reg([crime(data_infracao="01/01/2014", data_denuncia="01/02/2014", data_sentenca="01/03/2019", transito_mp="01/05/2019",
                     transito_processo="01/05/2019", pena_imposta=pena(2, 4))]))
confere(L["retro_status"].startswith("não configurada"), "2b: sem continuidade: %s" % L["retro_status"])
# pena sem o acréscimo informada pelo operador: vale a conta dela, sem a hipótese
ch2 = rp.chave_ajuste(c2, {})
L = linha(reg([c2], aj={ch2: {"valores": {"pena": "2a0m0d"}}}))
confere("Súmula 497), " not in L["retro_status"], "2c: pena informada pelo operador: %s" % L["retro_status"])

# ---------------- 3. textos da fuga / revogação / saldo zero ----------------
c3 = crime(data_infracao="01/01/2013", data_denuncia="01/02/2013", data_sentenca="01/06/2014", transito_mp="01/01/2015",
           transito_processo="01/01/2015")
L = linha(reg([c3], [ev("01/01/2015", "PRISÃO DEFINITIVA", proc=P1), ev("10/01/2016", "FUGA", tipo=INT), ev("01/03/2017", "RECAPTURA", proc=P1)],
              pena_total="1a0m0d", pena_cumprida="1a0m0d", pena_remanescente="0a0m0d"))
confere("interrompe (art. 117, V)" not in (L.get("ppe_detalhe") or "") or "saldo zero" not in (L.get("ppe_detalhe") or ""),
        "3: saldo zero com 'interrompe': %s" % L.get("ppe_detalhe"))
if L.get("ppe_saldo_zero"):
    confere("sem efeito na prescrição (saldo zero" in L["ppe_detalhe"], "3: saldo zero sem o texto novo: %s" % L["ppe_detalhe"])

# ---------------- 4. citações ----------------
src_p = open("rspe_prescricao.py", encoding="utf-8").read()
confere("STJ, Súmula 415; STF, Tema 438" in src_p, "4: Tema 438 ao lado da Súmula 415")
confere("a punitiva não recebe o aumento (STJ, Súmula 220)" in src_p, "4: Súmula 220")
confere("o STJ entende que a suspensão alcança também quem cumpre outra pena em livramento" in src_p, "4: HC 429.545 como posição contrária")
confere("STJ, Súmula 527)" not in src_p.replace("(STJ, Súmula 527).", ""), "4: Súmula 527 só como reforço da duração")
confere("Ponto discutível: a tese defensiva aplica o art. 113 por analogia" in src_p, "4: ponto discutível do art. 113 por analogia")
confere("(STJ, HC 429.545)" not in open("rspe_scraper.py", encoding="utf-8").read(), "4: HC 429.545 como apoio no scraper")
c4 = crime(lei="11343/06 - Lei de Drogas", artigo="ART 28: Posse para consumo", tipo_penal="CAPUT: Quem adquirir... para consumo pessoal",
           pena_imposta=pena(0), pena_total_processo="0a0m0d")
L = rp.analisar(reg([c4]), HOJE)["presc_linhas"][0]
confere(any("Tema 506" in a for a in L["avisos"]), "4: aviso do Tema 506 no art. 28: %s" % L["avisos"])

# ---------------- 5. saldo de 360 a 364 dias ----------------
confere(rv._soma_pena(date(2023, 2, 1), 729) == date(2025, 1, 30), "5: 01/02/2023 + 1a11m29d: %s" % rv._soma_pena(date(2023, 2, 1), 729))
confere(rv._soma_pena(date(2023, 2, 1), 365 + 60) == date(2024, 4, 1), "5: 1a2m sem mudança: %s" % rv._soma_pena(date(2023, 2, 1), 425))
r5 = reg([crime(pena_imposta=pena(4), pena_total_processo="4a0m0d - PENA ORIGINÁRIA", data_infracao="01/01/2020", transito_processo="01/01/2021",
                transito_mp="01/01/2021")],
         [ev("01/02/2021", "PRISÃO DEFINITIVA", proc=P1), ev("01/02/2023", "LIVRAMENTO CONDICIONAL", tipo=INT)],
         [inc("LIVRAMENTO CONDICIONAL", "01/02/2023"), inc("REVOGAÇÃO DE LIVRAMENTO CONDICIONAL", "03/02/2025")],
         pena_total="4a0m0d", pena_cumprida="2a0m1d", pena_remanescente="1a11m29d")
ex = rv.extincao(r5, {"presc_linhas": []}, True)
confere("30/01/2025" in ex["ext_hipoteses"] and "Súmula 617" in ex["ext_hipoteses"],
        "5: revogação em 03/02/2025, depois do fim do período de prova (30/01/2025): %s" % ex["ext_hipoteses"])

# ---------------- 6. término do SEEU alcançado depois de fuga ----------------
r6 = reg([crime(pena_imposta=pena(3), data_infracao="01/01/2021")],
         [ev("01/02/2022", "PRISÃO DEFINITIVA", proc=P1), ev("01/03/2024", "FUGA", tipo=INT)],
         pena_total="3a0m0d", pena_cumprida="2a1m0d", pena_remanescente="0a11m0d", termino_previsao_seeu="31/01/2025",
         situacao_cumprimento="PENA INTERROMPIDA (sem evento de reinício)")
ex = rv.extincao(r6, {"presc_linhas": []}, True)
confere(ex["ext_cor"] == "amarelo" and ex["ext_sit"] == "Extinção a verificar" and "interrompido antes dele, em 01/03/2024" in ex["ext_hipoteses"],
        "6: término do SEEU com fuga antes: %s | %s | %s" % (ex["ext_cor"], ex["ext_sit"], ex["ext_hipoteses"]))
r6b = dict(r6, _eventos=[ev("01/02/2022", "PRISÃO DEFINITIVA", proc=P1)], situacao_cumprimento="EM CUMPRIMENTO")
ex = rv.extincao(r6b, {"presc_linhas": []}, False)
confere(ex["ext_sit"] == "Extinção cabível", "6b: sem interrupção, segue cabível: %s" % ex["ext_sit"])

# ---------------- 7. detração exclusiva com outras penas ativas ----------------
_lin = {"ppe_detracao_cobre": True, "ppe_detracao_exclusiva": True, "proc_crim": P1, "crime": "art. 155 CP", "rotulo": "art. 155 CP",
        "ppe_detracao_dias": 400, "pena": "1a0m0d", "ppe_pena_processo": "1a0m0d"}
r7 = reg([crime(), crime(processo_criminal=P2, pena_imposta=pena(5))], pena_total="6a0m0d", pena_cumprida="1a0m0d", pena_remanescente="5a0m0d")
ex = rv.extincao(r7, {"presc_linhas": [dict(_lin)]}, False)
confere(ex["ext_cor"] != "vermelho" and "outras penas ativas" in ex["ext_hipoteses"], "7: execução unificada: %s | %s" % (ex["ext_cor"], ex["ext_hipoteses"]))
r7b = reg([crime()], pena_total="1a0m0d", pena_cumprida="0a0m0d", pena_remanescente="1a0m0d")
ex = rv.extincao(r7b, {"presc_linhas": [dict(_lin)]}, False)
confere(ex["ext_cor"] == "vermelho", "7b: condenação única segue cabível: %s" % ex["ext_cor"])

# ---------------- 8. ressalva do art. 89 ----------------
confere("Tema 1.367" in rv.TXT_ART89 and "Súmula 617" in rv.TXT_ART89 and "não prorroga" in rv.TXT_ART89, "8: ressalva do art. 89")

# ---------------- 9. data-base: crime no período sem trânsito nem falta ----------------
inc_prog = inc("PROGRESSÃO DE REGIME", "10/03/2022", "SEMIABERTO")
r9 = reg([crime(data_infracao="01/01/2020", transito_processo="01/01/2021", transito_mp="01/01/2021"),
          crime(processo_criminal=P2, data_infracao="01/06/2023", transito_processo="", transito_mp="", data_sentenca="")],
         [ev("01/01/2021", "PRISÃO DEFINITIVA", proc=P1), ev("01/02/2023", "ALVARÁ DE SOLTURA", tipo=INT), ev("05/06/2023", "PRISÃO EM FLAGRANTE")],
         [inc_prog], data_base="10/03/2022", pena_cumprida="2a0m0d")
d9, f9 = rv.data_base_calculada(r9)
confere(d9 == "10/03/2022" and "sem trânsito nem falta" in f9, "9: crime sem trânsito não move a data-base: %s (%s)" % (d9, f9))
confere(rv.data_base_info(r9, [])["db_cor"] == "amarelo", "9: a conferir (amarelo): %s" % rv.data_base_info(r9, []))
r9b = dict(r9, _crimes=[r9["_crimes"][0], dict(r9["_crimes"][1], transito_processo="01/02/2024", transito_mp="01/02/2024")])
confere(rv.data_base_calculada(r9b)[0] == "05/06/2023", "9b: com trânsito, a nova prisão: %s" % (rv.data_base_calculada(r9b),))

# ---------------- 10. conduta readquirida (LEP, art. 112, § 7º) ----------------
_itens = []


def add(ok, txt):
    _itens.append((ok, txt))


r10 = reg([crime()], falta_12m="SIM", falta_12m_detalhe="FALTA GRAVE (01/02/2026)", data_base_seeu="01/02/2026",
          progressao_previsao_seeu="01/10/2026")
rv._conduta_requisito(add, {"conduta": "BOA"}, "SIM", r10, HOJE)
confere(_itens and _itens[-1][0] is None and "112, § 7º" in _itens[-1][1], "10: conduta readquirida: %s" % _itens)
_itens.clear()
rv._conduta_requisito(add, {"conduta": "BOA"}, "SIM", dict(r10, progressao_previsao_seeu="01/02/2027"), HOJE)
confere(_itens and _itens[-1][0] is False, "10b: lapso ainda não vencido - não atende: %s" % _itens)

# ---------------- 11. data-base sem data de referência ----------------
r11 = rs.situacao_execucao({}, [ev("01/01/2021", "PRISÃO DEFINITIVA")], [inc("PROGRESSÃO DE REGIME", "10/03/2022", "SEMIABERTO", ref="")],
                           [crime()], HOJE) if "situacao_execucao" in rs.__dict__ else {}
if r11:
    confere(r11.get("data_base_sem_referencia") is True, "11: sem data de referência: %s" % r11)
r11b = reg([crime()], [ev("01/01/2021", "PRISÃO DEFINITIVA", proc=P1)], [inc("PROGRESSÃO DE REGIME", "10/03/2022", "SEMIABERTO", ref="")],
           data_base="10/03/2022", data_base_sem_referencia=True, pena_cumprida="1a0m0d")
_dbi = rv.data_base_info(r11b, [])
confere(_dbi["db_cor"] == "amarelo" and "Tema 1165" in _dbi["db_motivo"], "11: amarelo com o Tema 1165: %s" % _dbi)

# ---------------- 12. textos ----------------
src_s = open("rspe_scraper.py", encoding="utf-8").read()
confere("só impede se reconhecida (STJ, Tema 1195)" not in src_s, "12: fuga na coluna Falta com o Tema 1195")
confere("antes ainda com o desconto de" not in open("rspe_auditoria.py", encoding="utf-8").read(), "12: remição encurtando o art. 75")

if falhas:
    print("FALHOU (correção 7.15.2 - leitura e prazos):")
    for f in falhas:
        print("  " + f)
    sys.exit(1)
print("ok: correção 7.15.2, leitura e prazos (art. 366 sem fim, Súmula 497, revogação x fuga, saldo zero, citações, saldo de 360-364 dias, "
      "término com fuga, detração na execução unificada, art. 89, data-base sem trânsito, conduta readquirida, Tema 1165)")
