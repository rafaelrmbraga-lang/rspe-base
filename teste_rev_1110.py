"""Teste de regressão da revisão de 11/10/2026 (caso Alex): prisão encerrada na ficha por processo que integra o RSPE, sem cômputo
no RSPE, vira alerta de detração (só a partir do fato; não com prisão já computada nem por processo alheio); fuga e falta sem
sanção ficam como informação, não pendência; a linha do tempo do indulto diz para quais crimes cabe (crime e processo), traz o
resumo objetivo e a fundamentação também nos decretos da base (2000 a 2023).
Rodar: python teste_rev_1110.py"""
import sys
import types

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_indulto_tl as tl

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P1, P2 = "0000188-72.2022.8.12.0014", "0002296-45.2020.8.12.0014"


def reg(eventos, crimes=None):
    return {"_eventos": eventos, "_crimes": crimes or [
        {"processo_criminal": P2, "artigo": "ART 155: Furto", "lei": "2848/40 - Código Penal", "tipo_penal": "§ 1º: ...", "data_infracao": "10/11/2020"},
        {"processo_criminal": P1, "artigo": "ART 155: Furto", "lei": "2848/40 - Código Penal", "tipo_penal": "§ 4º: ...", "data_infracao": "25/01/2022"}]}


def ficha(evs, prisao="26/01/2022"):
    return {"data_prisao": prisao, "eventos": [{"data": d, "texto": t} for d, t in evs]}


E = "Entrada na Unidade Penal: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Procedente: DP MARACAJU - INTERIOR, Conforme OF/CI OF. 133/DP/MARACAJU/DGPC/2022."
S = "Saída da Unidade Penal: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Destino: 2ª VARA DE MARACAJU / MS, Motivo: Alvará de Soltura, Conforme Alvará: %s."
evs_rspe = [{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "data": "11/11/2020", "processos": P2}, {"tipo": "INTERRUPÇÃO", "data": "05/05/2021", "processos": ""},
            {"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "data": "24/01/2023", "processos": "0000180-61.2023.8.12.0014"}]
f = ficha([("03.02.2022", E), ("05.08.2022", S % P1), ("27.01.2023", E)])
it = rf._detracao_x_ficha(reg(evs_rspe), f)
ok(len(it) == 1 and it[0]["nivel"] == "alerta" and "26/01/2022 a 05/08/2022" in it[0]["titulo"] and "192 dias" in it[0]["titulo"], "Alex: %s" % it)
# soltura por processo que não está no RSPE: não é desta execução
ok(not rf._detracao_x_ficha(reg(evs_rspe), ficha([("03.02.2022", E), ("05.08.2022", S % "0000895-74.2021.8.12.0014")])), "processo alheio")
# período já computado no RSPE: nada a pedir
ok(not rf._detracao_x_ficha(reg([{"tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "data": "26/01/2022", "processos": P1}]), f), "já computado")
# prisão anterior ao fato do processo: conta só a partir do fato
f2 = ficha([("01.12.2021", E), ("05.08.2022", S % P1)], prisao="")
it = rf._detracao_x_ficha(reg(evs_rspe), f2)
ok(it and "25/01/2022 a 05/08/2022" in it[0]["titulo"] and "Preso desde 01/12/2021" in it[0]["detalhe"], "a partir do fato: %s" % it)

# linha do tempo: alcance e resumo objetivo
C = [{"id": "C1", "tipificacao": "Art. 155 § 1º, CP", "proc": P2, "selos": {"2023": {"selo": "NAO_IMPEDITIVO"}}},
     {"id": "C2", "tipificacao": "Art. 155 § 4º, CP", "proc": P1, "selos": {"2023": {"selo": "NAO_IMPEDITIVO"}}},
     {"id": "C3", "tipificacao": "Art. 33, Lei 11.343/06", "proc": "0000180-61.2023.8.12.0014", "selos": {"2023": {"selo": "FORA"}}}]
dd = {"id": "2023", "numero": "11.846", "referencia": "25/12/2023", "fora": [{"crime": "C3", "motivo": "sentença posterior à publicação (22/12/2023)"}],
      "cumprido": {"total": 500, "cumprimento": 0, "detracao": 507, "remicao": 0, "perda": 0}, "cumprido_txt": {"total": "1a4m22d"},
      "janela_falta": {"ini": "25/12/2022", "fim": "22/12/2023", "meses": 12}, "faltas": [],
      "indulto": {"status": "cabe", "rotulo": "Cabe · art. 2º, I", "pena_considerada_txt": "3a7m0d", "reinc": "reincidente", "checklist": [
          {"item": "Requisito objetivo / hipótese", "estado": "ok", "texto": "art. 2º, I: atendida - cumpridos 1a4m22d em 25/12/2023"},
          {"item": "Requisito objetivo / hipótese", "estado": "ko", "texto": "art. 2º, II: não atendida - pena total não supera 8 anos"}]}}
dd["alcance"] = tl._alcance(dd, C)
ok([c["id"] for c in dd["alcance"]["crimes"]] == ["C1", "C2"] and [c["id"] for c in dd["alcance"]["fora"]] == ["C3"], "alcance: %s" % dd["alcance"])
R = tl._resumo(dd, "indulto")
txt = "\n".join(R)
ok(P1 in txt and P2 in txt and "art. 2º, II" not in txt and "não houve falta grave de 25/12/2022 a 22/12/2023" in txt
   and R[-1] == "Resultado: Cabe o indulto (art. 2º, I) para C1 e C2.", "resumo: %s" % R)
cards = tl._consolidado([dict(dd, comutacao={})], C)
ok(any(l.startswith("Para: C1 - Art. 155 § 1º, CP, processo " + P2) for l in cards[0]["linhas"]), "cartão: %s" % cards)

# seção 5 (fundamentação): prosa por enquadramento, com o número e o ano do decreto, crimes e processos; um texto por inciso atendido
dd["indulto"]["checklist"].append({"item": "Requisito objetivo / hipótese", "estado": "ok", "det": {"evento": "condenadas em livramento condicional ou regime aberto"},
                                   "texto": "art. 2º, XIV: atendida - cumpridos 1a4m22d em 25/12/2023 (exigido 1a2m10d, 1/3)"})
dd["indulto"]["checklist"].append({"item": "Natureza dos crimes (vedações)", "estado": "ok", "texto": "Nenhum crime alcançado está no rol de vedações."})
nomes = {"C1": "art. 155 § 1º CP", "C2": "art. 155 § 4º CP", "C3": "art. 33 Lei 11.343/06"}
P = tl._peticao(dd, "indulto", nomes)
ok([o["rotulo"] for o in P] == ["art. 2º, I", "art. 2º, XIV"], "enquadramentos: %s" % [o["rotulo"] for o in P])
t = P[0]["texto"]
ok(t.startswith("DO INDULTO - Decreto nº 11.846/2023\n") and "Enquadra-se no art. 2º, I, do Decreto nº 11.846/2023" in t and P1 in t and P2 in t
   and "prosseguindo a execução quanto a art. 33 Lei 11.343/06 (processo 0000180-61.2023.8.12.0014)" in t and "C1" not in t and "art. 2º, II" not in t, "prosa: %s" % t)
ok("Enquadra-se no art. 2º, XIV" in P[1]["texto"], "segundo inciso: %s" % P[1]["texto"])
ok(not tl._peticao(dict(dd, indulto=dict(dd["indulto"], status="nao")), "indulto", nomes), "não cabe: sem texto")
# texto resumido dos decretos de 2024/2025 em prosa
c, conta, conf, alc = tl._cond_prosa("pena ≤ 8 anos sem VGA, exige 1/5 (cumprido 0a11m9d de 1a2m0d).")
ok(c == "pena não superior a 8 anos por crime sem violência ou grave ameaça, com 1/5 da pena cumprida" and conta == "cumpridos 11 meses e 9 dias de pena de 1 ano e 2 meses",
   "prosa 2025: %s | %s" % (c, conta))

if falhas:
    print("FALHOU (revisão 11/10):\n  " + "\n  ".join(falhas))
    sys.exit(1)
print("ok: revisão 11/10 (detração da ficha por processo do RSPE, alcance do indulto, resumo objetivo, cartão do resultado, fundamentação por enquadramento)")
