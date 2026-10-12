"""Leitura da ficha e do RSPE (auditoria da leitura de 12/10/2026, erros E1 a E7), com lançamentos sintéticos (sem dados pessoais):
E1 vínculos simultâneos (o setor encerrado só pelo início de outro vai até a sua baixa; não reabre por cima de saída, desligamento,
remanejamento ou liberação; a remição conta o dia uma vez), E2 setor vazio ("no setor de trabalho , conforme documento"), E3 período
do atestado ("com data inicial em d e final em d", "início em d e término em d", "de (d) a (d)", nome começando por algarismo ou com
apóstrofo, trecho do ATP com vírgula, sem "DATA" ou sem "DATA INICIAL"), E4 fim de isolamento fora da lista de isolamentos, E5 saídas
temporárias (aspas, "RETONROU", "no período de d a d", "beneficiado ... retornou"), E6 "Entrada no Regime X da Unidade Penal" e E7
número provisório de 13 dígitos do SEEU no lugar do CPF. Rodar: python teste_leitura_rev1210.py"""
import copy
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf  # noqa: E402
import rspe_remicao as rrm  # noqa: E402
import rspe_scraper as rs  # noqa: E402

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)
    return cond


def ficha(evs):
    f = {"versao_leitura": 0, "eventos": [{"data": d, "texto": t} for d, t in evs]}
    return rf.atualizar(f)


def trab(f):
    return [(t["inicio"], t.get("fim") or "", t["setor"]) for t in f["trabalho"]]


INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento CI 1/2024."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento CI 2/2024, motivo: %s."

ok(rf.VERSAO_LEITURA >= 12, "VERSAO_LEITURA subiu (releitura das fichas gravadas)")

# ---- E1: dois setores ao mesmo tempo ----
f = ficha([("04.01.2022", INI % "CANTINA"), ("02.03.2022", INI % "SERVIÇOS GERAIS"),
           ("24.03.2022", FIM % ("SERVIÇOS GERAIS", "DESLIGADO")),
           ("24.03.2022", "Liberação do Setor de Trabalho - Doc.: CI 3/2024 Motivo: DESLIGADO"),
           ("10.05.2023", FIM % ("CANTINA", "TROCA DE FUNÇÃO"))])
t = trab(f)
ok(("04.01.2022", "10.05.2023", "CANTINA") in t, "E1: o setor vai até a sua baixa (sem lacuna falsa): %s" % t)
ok(("02.03.2022", "24.03.2022", "SERVIÇOS GERAIS") in t, "E1: o segundo setor com o seu período: %s" % t)
ok(not f["baixas_sem_inicio"], "E1: a baixa do primeiro setor não fica órfã: %s" % f["baixas_sem_inicio"])
ok(any(x.get("simultaneo") for x in f["trabalho"]), "E1: vínculo marcado como simultâneo")
# saída da unidade, desligamento sem setor ou remanejamento no meio: a baixa tardia não reabre
for meio in ("Saída da Unidade Penal: UNIDADE A, Destino: UNIDADE B, Motivo: Transferência de Presidio, Conforme Ofício: 1.",
             "DESLIGADO DO TRABALHO POR IMPRODUTIVIDADE.", "FOI REMANEJADO INTERNAMENTE PARA A EMPRESA X, CONFORME CI 5/2024.",
             "Liberação do Setor de Trabalho - Doc.: CI 4/2024 Motivo: OPERACIONAL"):
    f = ficha([("04.01.2022", INI % "CANTINA"), ("02.03.2022", INI % "HORTA"), ("10.06.2022", meio),
               ("10.05.2023", FIM % ("CANTINA", "N/C"))])
    ok(("04.01.2022", "02.03.2022", "CANTINA") in trab(f) and f["baixas_sem_inicio"], "E1: não reabre por cima de '%s': %s" % (meio[:30], trab(f)))
# desligamento de OUTRO setor nomeado no meio: não corta
f = ficha([("04.01.2022", INI % "ARTESANATO"), ("02.03.2022", INI % "ALPARGATAS"),
           ("10.06.2022", "DESLIGADO DE ATIVIDADE LABORAL, DO SETOR DE OFICINA ALPARGATAS, DEVIDO A PARALISAÇÃO."),
           ("10.05.2023", FIM % ("ARTESANATO", "N/C"))])
ok(("04.01.2022", "10.05.2023", "ARTESANATO") in trab(f), "E1: desligamento de outro setor não corta: %s" % trab(f))
# "adequação do mapa do SIAPEN" é correção de cadastro: não reabre
f = ficha([("04.05.2023", INI % "FABRICA"), ("04.05.2023", INI % "EMPRESA X"), ("18.06.2026", FIM % ("FABRICA", "ADEQUAÇÃO DO MAPA DO SIAPEN"))])
ok(not any(x.get("simultaneo") for x in f["trabalho"]) and any("FABRICA / EMPRESA X" == x["setor"] for x in f["trabalho"]),
   "E1: adequação do mapa não reabre (linha do mesmo dia): %s" % trab(f))
# a baixa no mesmo dia do início do outro: só registra o motivo
f = ficha([("01.02.2024", INI % "COZINHA"), ("01.03.2024", INI % "COPA"), ("01.03.2024", FIM % ("COZINHA", "TROCA DE FUNÇÃO"))])
v = [x for x in f["trabalho"] if x["setor"] == "COZINHA"][0]
ok(v["fim"] == "01.03.2024" and v["motivo_fim"] == "TROCA DE FUNÇÃO" and not v.get("simultaneo") and not f["baixas_sem_inicio"],
   "E1: baixa no mesmo dia: %s %s" % (v, f["baixas_sem_inicio"]))
# remição: setores em paralelo, o mesmo dia conta uma vez
evs = [{"data": d, "texto": t} for d, t in (("04.01.2022", INI % "CANTINA"), ("02.03.2022", INI % "HORTA"),
                                            ("31.03.2022", FIM % ("HORTA", "N/C")), ("30.04.2022", FIM % ("CANTINA", "N/C")))]
vs, _av = rrm.vinculos(evs, date(2026, 10, 12))
per = sorted((x["ini"], x["fim"]) for x in vs)
ok(per == [(date(2022, 1, 4), date(2022, 4, 30)), (date(2022, 3, 2), date(2022, 3, 31))], "E1: vínculos da remição: %s" % per)
uniao = set().union(*(rrm._dias_set(x["ini"], x["fim"]) for x in vs))
ok(len(uniao) == len(rrm._dias_set(date(2022, 1, 4), date(2022, 4, 30))), "E1: dias da remição sem dobra: %d" % len(uniao))
ok(rf._dias_no_intervalo([(date(2024, 1, 1), date(2024, 1, 31)), (date(2024, 1, 10), date(2024, 2, 9))], date(2024, 1, 1), date(2024, 12, 31)) == 40,
   "E1: trabalho externo simultâneo (inciso XI) sem dobra")

# ---- E2: setor vazio ----
f = ficha([("24.04.2025", "TRABALHO: Iniciou atividade laboral, no setor de trabalho , conforme documento 001."),
           ("02.05.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho , conforme documento , motivo: Saida do Presídio.")])
ok(trab(f) == [("24.04.2025", "02.05.2025", "")] and not f["baixas_sem_inicio"], "E2: setor vazio: %s %s" % (trab(f), f["baixas_sem_inicio"]))
ok(not any("CONFORME" in x["setor"].upper() for x in f["trabalho"]), "E2: 'CONFORME DOCUMENTO' não vira setor")
f = ficha([("24.04.2025", INI % "HORTA"), ("02.05.2025", "TRABALHO: Deixa de trabalhar, no setor de trabalho , conforme documento , motivo: N/C.")])
ok(trab(f) == [("24.04.2025", "02.05.2025", "HORTA")], "E2: baixa sem setor encerra o único vínculo aberto: %s" % trab(f))


# ---- E3: período do atestado ----
def segs(txt, d="20.11.2017"):
    a = rrm.atestados([{"data": d, "texto": txt}])
    return a[0] if a else None


a = segs("Nesta data foi expedido Atestado de Trabalho Prisional nº 63/2017 com data inicial em 06/06/2017 e final em 18/11/2017, "
         "totalizando 140 dias trabalhados e 46 remidos.")
ok(a and not a["lote"] and (a["segs"][0]["ini"], a["segs"][0]["fim"]) == (date(2017, 6, 6), date(2017, 11, 18)), "E3: inicial em/final em: %s" % a)
a = segs("NESTA DATA FOI EMITIDO ATP N 218/2026 COM INÍCIO EM 03.03.2026 E TÉRMINO EM 15.05.2026 SENDO 64 DIAS TRABALHADOS E 21 REMIDOS, "
         "SETOR DE FAXINA DA PORTARIA.", "10.07.2026")
ok(a and not a["lote"] and (a["segs"][0]["ini"], a["segs"][0]["fim"]) == (date(2026, 3, 3), date(2026, 5, 15)), "E3: início em/término em: %s" % a)
a = segs("Nesta data foi peticionado o atestado de trabalho nº 034/2022, referente ao Setor de Confecção de prendedores de (26/02/2020) a "
         "(17.03.2022), sendo 535 dias trabalhados e 178,33 dias remidos.", "24.03.2022")
ok(a and not a["lote"] and (a["segs"][0]["ini"], a["segs"][0]["fim"]) == (date(2020, 2, 26), date(2022, 3, 17)), "E3: de (d) a (d): %s" % a)
a = segs("EMITIDO ATESTADO DE TRABALHO PRISIONAL Nº1622/2022, REFERENTE AO PERÍODO TRABALHADO NA EMPRESA ALFA 08/05/2020 15/05/2020 - "
         "BETA GAMA 29/05/2020 18/06/2020 - 1A SERVIÇOS DE OBRAS 07/06/2022 07/07/2022 , TOTALIZANDO 44 DIAS TRABALHADOS E 14,67 DIAS REMIDOS.", "30.09.2022")
ok(a and [s["fim"] for s in a["segs"]][-1:] == [date(2022, 7, 7)] and len(a["segs"]) == 3, "E3: nome começando por algarismo: %s" % (a and a["segs"]))
a = segs("EMITIDO ATESTADO DE TRABALHO PRISIONAL Nº1242/2023, REFERENTE AO PERÍODO TRABALHADO NA EMPRESA ALFA 22/06/2023 15/08/2023 - "
         "PASTEL D’OURO 16/10/2023 06/12/2023, TOTALIZANDO 90 DIAS TRABALHADOS E 30 DIAS REMIDOS.", "07.12.2023")
ok(a and len(a["segs"]) == 2 and a["segs"][-1]["fim"] == date(2023, 12, 6), "E3: nome com apóstrofo: %s" % (a and a["segs"]))
a = segs("Emitido Atestado de Trabalho Prisional n. 153/2023; COSTURA DE BOLA, Data inicial: 06.08.2022; Data Final: 14.01.2023; PRENDEDORES DE "
         "ROUPAS: DATA INICIAL: 15.01.2023; DATA FINAL: 23.06.2023; Tempo de Trabalho 138 dias; Tempo de remição: 46 dias.", "23.06.2023")
ok(a and [(s["ini"], s["fim"]) for s in a["segs"]] == [(date(2022, 8, 6), date(2023, 1, 14)), (date(2023, 1, 15), date(2023, 6, 23))],
   "E3: ATP com vírgula antes de DATA: %s" % (a and a["segs"]))
a = segs("EMITIDO ATP Nº 255/2023 - PRENDEDORES DE ROUPAS - DATA INICIAL: 02.05.23 à 29.07.23; Costura de Bolas: de 29.07.23 à 23.10.23; "
         "TEMPO DE TRABALHO: 150 DIAS; TEMPO DE REMIÇÃO: 50 DIAS REMIDOS.", "23.10.2023")
ok(a and len(a["segs"]) == 2 and a["segs"][1]["fim"] == date(2023, 10, 23), "E3: ATP com trecho sem 'DATA': %s" % (a and a["segs"]))
a = segs("- EMITIDO ATP Nº 105/2025; PRENDEDORES DE ROUPAS: 04/12/2024; DATA FINAL: 11/06/2025; TEMPO DE TRABALHO COMPUTADO NO PERÍODO: 163 DIAS "
         "TRABALHADOS; TEMPO DE REMIÇÃO: 54,33 DIAS REMIDOS.", "11.06.2025")
ok(a and not a["lote"] and (a["segs"][0]["ini"], a["segs"][0]["fim"]) == (date(2024, 12, 4), date(2025, 6, 11)), "E3: ATP sem 'DATA INICIAL': %s" % a)
a = segs("EMITIDO ATP Nº 208/2022; ARTESANATO; TEMPO DE TRABALHO: 07.10.2021 A 22.06.2022; 222 DIAS TRABALHADOS: 74 DIAS REMIDOS.", "22.06.2022")
ok(a and a["segs"][0]["setor"] == "" and a["segs"][0]["ini"] == date(2021, 10, 7), "E3: 'TEMPO DE TRABALHO: d a d' não vira setor: %s" % (a and a["segs"]))
a = segs("ATESTADO DE TRABALHO PRISIONAL - Nesta data foi PROTOCOLADO o Atestado de Trabalho Prisional n°196/2022. Data Inicial 01/10/2021 até Data "
         "Final 28/10/2021 no SETOR DE OLARIA, Data Inicial 16/12/2021 até Data Final 03/05/2022 no SETOR DE COPA e Data Inicial 04/05/2022 até "
         "Data Final 30/06/2022 no SETOR DE COZINHA, no qual consta um total de 213 dias trabalhados, visto que o tempo de REMIÇÃO totalizou 71,00 dias.",
         "20.07.2022")
ok(a and len(a["segs"]) == 3 and a["segs"][0]["setor"], "E3: 'Data Inicial ... no SETOR DE X' com 3 trechos segue lido: %s" % (a and a["segs"]))
ok(a and a["trab"] == 213 and a["rem"] == 71.0, "E3: dias do atestado inalterados")

# ---- E4: fim de isolamento ----
for t in ("Retornou ao convívio após cumprir isolamento preventivo em cela disciplinar, conforme CI 1/2015.",
          "TERMINO DO ISOLAMENTO DISCIPLINAR CONFORME CHEFE DE DISCIPLINA, POREM PERMANECE EM CELA DISCIPLINAR.",
          "SAI DA CELA DISCIPLINAR E PASSA A CONDIÇÃO DE SANCIONADO ATÉ 07/09/2014 - CI 1/2014.",
          "Mudança de Cela: UNIDADE A, Motivo: SAI DA CELA DISCIPLINAR E FICA SANCIONADO ATE 24/02/2015, Origem: C/1, Destino: D/2, Conforme Documento: CI 1."):
    ok(not rf._e_isolamento(t), "E4: fim de isolamento não é isolamento: %s" % t[:50])
for t in ("Foi afastado das atividades laborais e isolado preventivamente em Cela Disciplinar.",
          "Nesta data foi assinado advertência disciplinar, permanecendo isolado em cela disciplinar pelo prazo de 10 dias, devendo retornar ao convívio "
          "na data de 27/08/2018.",
          "Nesta data o interno declarou que quer retornar ao convívio; solicitou para ser isolado em cela disciplinar."):
    ok(rf._e_isolamento(t), "E4: isolamento segue na lista: %s" % t[:50])

# ---- E5: saídas temporárias ----
casos = [
    ([("02.11.2018", "Nesta data o preso foi beneficiado com a saída temporária, do dia 02/11/2018 a 06/11/2018."),
      ("07.11.2018", 'Nesta data o interno retornou da "SAÍDA TEMPORÁRIA".')], [date(2018, 11, 7)]),
    ([("02.12.2021", "RETONROU DA SAÍDA TEMPORÁRIA DE 07 (SETE) DIAS.")], [date(2021, 12, 2)]),
    ([("21.12.2016", "Saida Temporaria (natal / ano novo) no periodo de 21/12/16 a 27/12/16.")], [date(2016, 12, 21)]),
    ([("11.01.2024", "Saída Temporária, conforme determinação judicial na mov. 153.1 no período de 23/12/2023 à 30/12/23")], [date(2023, 12, 23)]),
    ([("09.05.2023", "FOI BENEFICIADO COM SAÍDA TEMPORÁRIA PELO PRAZO DE 7 (SETE) DIAS, DEVENDO RETORNAR A ESTA UNIDADE PENAL NA DATA DE 15/05/2023."),
      ("15.05.2023", "FOI BENEFICIADO COM SAÍDA TEMPORÁRIA DE 07 (SETE) DIAS, NO QUAL RETORNOU À ESTÁ UNIDADE PENAL NA DATA DE 15/05/2023.")],
     [date(2023, 5, 15)]),
    ([("11.10.2024", "Retornou nesta data, do benefício de saída temporária, de 07 (sete) dias. Sem alteração.")], [date(2024, 10, 11)]),
    ([("13.01.2025", "FOI BENEFICIADO EM 31/12/2024 COM SAÍDA TEMPORARIA DE ANO NOVO, CONFORME PORTARIA. RETORNANDO EM 02/01/2025, SEM ALTERAÇÃO.")],
     [date(2025, 1, 2)]),
    # concessão sem saída nem retorno registrados: não entra (a decidir)
    ([("14.12.2015", "BENEFICIADO JUDICIALMENTE COM SAÍDA TEMPORÁRIA DE 7 DIAS - OF. 1/2015 - DEVENDO RETORNAR EM 21/12/15.")], []),
    ([("22.12.2018", "O interno foi lançado como saída temporária, porém não pode sair por motivos financeiro.")], []),
]
for evs, esp in casos:
    e = [{"data": d, "texto": t} for d, t in evs]
    ok(rf.saidas_temporarias(e) == esp, "E5: %s -> %s (esperado %s)" % (evs[-1][1][:50], rf.saidas_temporarias(e), esp))
e = [{"data": "11.01.2024", "texto": "Saída Temporária, conforme determinação judicial no período de 23/12/2023 à 30/12/23"}]
ok(rf.saidas_temporarias_retorno(e) == [(date(2023, 12, 23), date(2023, 12, 30))], "E5: saída e retorno pelo período: %s" % rf.saidas_temporarias_retorno(e))
# o formato antigo continua
e = [{"data": "10.08.2026", "texto": "Saída confirmada do benefício de: SAÍDA TEMPORÁRIA"},
     {"data": "17.08.2026", "texto": "Retorno confirmado do benefício de: SAÍDA TEMPORÁRIA"}]
ok(rf.saidas_temporarias(e) == [date(2026, 8, 10)] and rf.saidas_temporarias_retorno(e) == [(date(2026, 8, 10), date(2026, 8, 17))],
   "E5: formato estruturado")

# ---- E6: entrada "no Regime X da Unidade Penal" ----
f = {"eventos": [{"data": "06.04.2017", "texto": "Entrada no Regime Semiaberto da Unidade Penal: ESTABELECIMENTO PENAL DE REGIME SEMIABERTO, "
                                                 "ABERTO E ASSISTÊNCIA AO ALBERGADO DE CIDADE X, Procedente: PENITENCIÁRIA Y - INTERIOR, conforme OFÍCIO 1."},
                 {"data": "01.02.2016", "texto": "Entrada na Unidade Penal: PENITENCIÁRIA Y, Procedente: DELEGACIA Z, conforme ofício 2."}]}
tl = rf.linha_unidades(f)
ok([d for d, _u in tl] == [date(2016, 2, 1), date(2017, 4, 6)] and tl[1][1].startswith("ESTABELECIMENTO PENAL DE REGIME SEMIABERTO, ABERTO"),
   "E6: entrada no regime da unidade: %s" % tl)
ok(rf.RE_ENTRADA.search(f["eventos"][0]["texto"]), "E6: RE_ENTRADA reconhece a entrada no regime")

# ---- E7: número provisório do SEEU no lugar do CPF ----
ok(rs.cpf_rspe("1612345678901") == "não informado (registro provisório do SEEU nº 1612345678901)", "E7: rótulo do número provisório")
ok(rs.cpf_rspe("123.456.789-09") == "123.456.789-09" and rs.cpf_rspe("") == "" and rs.cpf_rspe("Não informado") == "Não informado", "E7: CPF normal intacto")
ok(rs.cpf_rspe(rs.cpf_rspe("1612345678901")) == rs.cpf_rspe("1612345678901"), "E7: idempotente")
r = {"processo_execucao": "0000001-01.2020.8.12.0001", "nome": "PESSOA TESTE", "cpf": "1612345678901", "data_geracao_rspe": "01/10/2026",
     "regime_atual": "Fechado - ATIVO", "pena_total": "8a0m0d", "pena_cumprida": "3a0m0d", "pena_remanescente": "5a0m0d",
     "versao_leitura_rspe": rs.VERSAO_LEITURA_RSPE,
     "_crimes": [{"processo_criminal": "0000001-01.2020.8.12.0001", "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
                  "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "8 ano(s), 0 mês(es) e 0 dia(s)",
                  "pena_total_processo": "8 ano(s), 0 mês(es) e 0 dia(s)", "data_infracao": "10/01/2020", "data_denuncia": "10/02/2020",
                  "data_sentenca": "10/06/2020", "transito_mp": "10/07/2020", "transito_processo": "10/07/2020", "extinto": "Não", "suspenso": "Não",
                  "vga": "N", "resultado_morte": "N", "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N",
                  "fracao_progressao": "16% - Art.112, I, da LEP", "fracao_livramento": "1/3 - Comum"}],
     "_incidentes": [], "_eventos": [{"tipo": "PRISÃO", "motivo": "PRISÃO EM FLAGRANTE", "data": "01/10/2023", "processos": "0000001-01.2020.8.12.0001"}]}
x = rs.reprocessar(copy.deepcopy(r))
ok(x["cpf"].startswith("não informado (registro provisório do SEEU"), "E7: registro gravado antes é rotulado ao abrir: %s" % x["cpf"])
ok("".join(c for c in x["cpf"] if c.isdigit()) == "1612345678901", "E7: os 13 dígitos seguem para o confronto de identidade (rji)")
try:
    import rspe_app as app
    ok("rji:1612345678901" in app._chaves_pessoa(x) and not any(k.startswith("cpf:") for k in app._chaves_pessoa(x)),
       "E7: chaves de identidade: %s" % app._chaves_pessoa(x))
except ImportError:
    pass

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f_ in falhas:
        print(" -", f_)
    sys.exit(1)
print("teste_leitura_rev1210: ok")
