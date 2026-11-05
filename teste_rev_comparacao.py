"""Correção 7.15.2, comparação com conferências manuais (aba Ficha/remição): (1) vínculo aberto no mesmo dia de outro setor e sem baixa
própria fica "a conferir, sem dias" depois da baixa do outro setor (provável registro duplicado), e não "pedir atestado"; (2) remição do
RSPE de valor diferente, decidida até 30 dias depois do atestado, fica ligada a ele ("remido a menor/maior que o atestado: conferir a
decisão"), e não "sem registro de peticionamento" - sem roubar a remição de outro documento nem a de um atestado com dois trechos;
(3) número dos autos com erro de digitação na ficha (segmento do tribunal ou até 2 algarismos com dígito verificador inválido) não manda
o atestado para "à parte"; (4) reinscrição ("Iniciou" e "Deixa" do mesmo setor no mesmo dia, com a baixa real depois) não encerra o
vínculo. Casos hipotéticos, sem nomes. Rodar: python teste_rev_comparacao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0000001-11.2018.8.12.0001"


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def rem(n, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % n, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def R(*incs, ini="01/07/2018"):
    r = {"processo_execucao": PROC, "_crimes": [], "_eventos": [{"data": ini, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}],
         "_incidentes": list(incs)}
    rr = sum(float(i["complemento"].split()[0]) for i in incs if i["tipo"] == "REMIÇÃO")
    r["saldo_remidos"] = "%g dias (%g dias remidos - 0 dias perdidos)" % (rr, rr)
    return r


def F(eventos, impressao="06/10/2026"):
    f = rf.atualizar({"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]})
    for k in ("leituras", "exames", "cursos_peticionados", "certidoes_estudo"):
        f.setdefault(k, [])
    return f


def N_(r, f):
    return rf.comparativo(r, f, HOJE)["fd_novo"]


INI = lambda s: "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento N/C." % s
FIM = lambda s, m="DESISTIU POR OPÇÃO PROPRIA": "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento N/C, motivo: %s ." % (s, m)


def doc(N, num):
    return next(d for d in N["docs"] if d["num"].startswith(num))


try:
    # ---- (1) "Ajudante" aberto com o "Prendebem" e nunca baixado: depois da baixa do Prendebem, a conferir sem dias ----
    f = F([("03.02.2020", INI("AJUDANTE")), ("03.02.2020", INI("PRENDEBEM/PDIB")),
           ("10.02.2021", "Peticionado o Atestado de trabalho n 010/2021, no Sistema SEEU, Autos %s, função Prendebem (03/02/2020 a 09/02/2021) "
                          "totalizando 300 dias trabalhados e 100 dias remidos." % PROC),
           ("15.04.2021", FIM("PRENDEBEM/PDIB")), ("15.04.2021", "Liberação do Setor de Trabalho - Doc.: N/C Motivo: DESISTIU POR OPÇÃO PROPRIA"),
           ("06.03.2023", INI("PRENDEBEM/PDIB")), ("28.07.2023", FIM("PRENDEBEM/PDIB", "IMPRODUTIVIDADE"))])
    N = N_(R(rem(100, "10/03/2021")), f)
    L = N["trab"]["linhas"]
    dup = [x for x in L if x.get("dup")]
    ok(dup and dup[0]["local"].startswith("Ajudante") and dup[0]["ini"] == date(2021, 4, 16) and not dup[0].get("pedir_dias")
       and not dup[0].get("talvez_dias") and not dup[0].get("conf_dias"), "1: linha duplicada: %s" % [(x["local"], x["periodo"], x.get("dup")) for x in L])
    # o pedido fica só com o trabalho real (Prendebem 10/02 a 15/04/2021 e 06/03 a 28/07/2023)
    real = rf.dias_jornada_set(date(2021, 2, 10), date(2021, 4, 15)) | rf.dias_jornada_set(date(2023, 3, 6), date(2023, 7, 28))
    ok(abs(N["pedir_dias"] - len(real) / 3.0) < 0.01, "1: pedir só o trabalho real: %s x %s" % (N["pedir_dias"], len(real) / 3.0))
    ok(any(p["tipo"] == "duplicado" and "provável registro duplicado" in p["texto"] for p in N["pontos"]), "1: ponto: %s" % [p["tipo"] for p in N["pontos"]])
    linhas = rf.comparativo(R(rem(100, "10/03/2021")), f, HOJE)["fd_linhas"]
    ok(any("provável registro duplicado" in x["sit"] and x["cor"] == "cinza" for x in linhas), "1: linha exportada: %s" % [x["sit"] for x in linhas])
    # dois setores no mesmo dia, a baixa só do segundo e nada depois: o primeiro segue em curso (trabalho atual, não duplicado)
    f = F([("01.04.2026", INI("POLIGONAL ENGENHARIA LTDA")), ("01.04.2026", INI("SERRALHERIA")), ("19.06.2026", FIM("SERRALHERIA", "REMANEJAMENTO"))])
    N = N_(R(), f)
    ok(not any(x.get("dup") for x in N["trab"]["linhas"]), "1: em curso sem nada depois não é duplicado: %s" % N["trab"]["linhas"])
    # o vínculo com baixa própria (simultâneo de verdade) não é duplicado
    f = F([("01.03.2025", INI("COZINHA")), ("01.03.2025", INI("FAXINA")), ("30.04.2025", FIM("FAXINA")), ("30.09.2025", FIM("COZINHA"))])
    N = N_(R(), f)
    ok(not any(x.get("dup") for x in N["trab"]["linhas"]), "1: com baixa própria não é duplicado: %s" % [(x["local"], x["periodo"]) for x in N["trab"]["linhas"]])

    # ---- (2) remição de valor diferente decidida logo depois do atestado ----
    ev2 = [("15.10.2025", INI("PRENDEBEM/PDIB")),
           ("12.06.2026", "TRABALHO, nesta data foi emitido atestado de trabalho nº061/PDIB/AGEPEN/MS setor de PRENDE BEM com 75 dias de remição.")]
    N = N_(R(rem(66, "19/06/2026")), F(ev2))
    d = doc(N, "061")
    ok(d["sit"].startswith("Provavelmente apreciado em 19/06/2026") and "remido a menor" in d["sit"] and d["cor"] == "amarelo",
       "2: remido a menor: %s / %s" % (d["sit"], d["cor"]))
    ok(not any(p["tipo"] == "sem_pet" for p in N["pontos"]) and any(p["tipo"] == "remida_diferente" for p in N["pontos"]),
       "2: sem 'sem peticionamento': %s" % [p["tipo"] for p in N["pontos"]])
    # um pouco a mais (40 x 44, 10 dias depois): remido a maior
    N = N_(R(rem(44, "30/08/2026")), F([("10.03.2026", INI("POLIGONAL ENGENHARIA LTDA")),
                                        ("20.08.2026", "TRABALHO, nesta data foi emitido at n 207 poligonal engenharia ltda com 40 dias remidos")]))
    ok("remido a maior" in doc(N, "207")["sit"], "2: remido a maior: %s" % doc(N, "207")["sit"])
    # decidida mais de 30 dias depois: não liga
    N = N_(R(rem(66, "30/07/2026")), F(ev2))
    ok("apreciado" not in doc(N, "061")["sit"], "2: fora da janela: %s" % doc(N, "061")["sit"])
    # outro documento emitido nos 30 dias antes da decisão: a remição pode ser dele - não liga
    N = N_(R(rem(66, "19/06/2026")), F(ev2 + [("15.06.2026", "Peticionado Certificado do ENCCEJA 2025 no Sistema SEEU")]))
    ok("apreciado" not in doc(N, "061")["sit"], "2: outro documento perto: %s" % doc(N, "061")["sit"])
    # atestado com dois trechos e duas remições no mesmo dia que somam o atestado: não liga uma delas como "a menor"
    f = F([("15.07.2024", INI("POLIGONAL ENGENHARIA LTDA")),
           ("04.05.2026", "Peticionado o Atestado de Trabalho n 050/2026, no Sistema SEEU, Autos %s, função Poligonal Engenharia (15/07/2024 a "
                          "30/04/2025) 180 dias trabalhados e 60 remidos; (02/06/2025 a 04/05/2026) 210 dias trabalhados e 70 remidos." % PROC)])
    N = N_(R(rem(60, "12/05/2026"), rem(70, "12/05/2026")), f)
    ok("apreciado" not in doc(N, "050")["sit"], "2: atestado de dois trechos: %s" % doc(N, "050")["sit"])
    # a remição bate com os dias trabalhados ÷ 3 do próprio atestado: a conta do atestado é que parece errada (cinza)
    f = F([("05.06.2023", INI("HORTA")),
           ("20.05.2025", "Peticionado O Atestado de Trabalho n 077/2025, no Sistema SEEU, Autos %s, função Horta (05/06/2023 a 30/04/2025) "
                          "540 dias trabalhados e 280 remidos." % PROC)])
    d = doc(N_(R(rem(180, "29/05/2025")), f), "077")
    ok("conferir a conta do atestado" in d["sit"] and d["cor"] == "cinza", "2: conta do atestado: %s / %s" % (d["sit"], d["cor"]))

    # ---- (3) número dos autos com erro de digitação na ficha ----
    ok(rrm.autos_quase("00000011120188090001", {"00000011120188120001"}) == "00000011120188120001", "3: segmento do tribunal")
    ok(not rrm.autos_quase("00000022220188120001", {"00000011120188120001"}), "3: outro processo")
    # um algarismo trocado com dígito verificador inválido: erro; com dígito verificador válido: outro processo
    ok(rrm.autos_quase("00000011120178120001", {"00000011120188120001"}), "3: algarismo trocado, DV inválido")
    real_ = "0000002" + rrm._dv_cnj("00000020020188120001") + "20188120001"
    ok(not rrm.autos_quase(real_, {"00000011120188120001"}), "3: número válido de outro processo")
    f = F([("03.10.2022", INI("ARTESANATO")),
           ("25.10.2023", "Peticionado o Atestado de trabalho n 214/23, no Sistema SEEU, Autos 0000001-11.2018.8.09.0001, função Artesanato (03/10/2022 a "
                          "20/10/2023) totalizando 240 dias trabalhados e 80 dias remidos.")])
    d = doc(N_(R(rem(80, "15/02/2024")), f), "214")
    ok(not d["fora"] and "número dos autos divergente na ficha" in d["sit"], "3: atestado nestes autos: %s / %s" % (d["fora"], d["sit"]))
    f = F([("03.10.2022", INI("ARTESANATO")),
           ("25.10.2023", "Peticionado o Atestado de trabalho n 214/23, no Sistema SEEU, Autos 0009999-55.2019.8.12.0002, função Artesanato (03/10/2022 a "
                          "20/10/2023) totalizando 240 dias trabalhados e 80 dias remidos.")])
    ok(doc(N_(R(), f), "214")["fora"].startswith("dirigido a outros autos"), "3: outros autos de verdade continuam à parte")

    # ---- (4) reinscrição: "Iniciou" e "Deixa" do mesmo setor no mesmo dia, com a baixa real depois ----
    f = F([("12.08.2024", INI("POLIGONAL ENGENHARIA LTDA")),
           ("19.11.2024", INI("POLIGONAL ENGENHARIA LTDA")), ("19.11.2024", FIM("POLIGONAL ENGENHARIA LTDA", "DISPENSADO PELO EMPREGADOR")),
           ("19.11.2024", "Liberação do Setor de Trabalho - Doc.: N/C Motivo: DISPENSADO PELO EMPREGADOR"),
           ("14.07.2026", FIM("POLIGONAL ENGENHARIA LTDA", "DISPENSADO PELO EMPREGADOR"))])
    tr = [(t["setor"], t["inicio"], t.get("fim")) for t in f["trabalho"]]
    ok(tr == [("POLIGONAL ENGENHARIA LTDA", "12.08.2024", "14.07.2026")] and not f.get("baixas_sem_inicio"), "4: vínculo contínuo: %s" % tr)
    # com outro setor no meio (o anterior encerrado pelo início dele) também
    f = F([("08.01.2024", INI("POLIGONAL ENGENHARIA LTDA")), ("05.05.2025", INI("TRABALHO EXTERNO")),
           ("05.05.2025", INI("POLIGONAL ENGENHARIA LTDA")), ("05.05.2025", FIM("POLIGONAL ENGENHARIA LTDA", "N/C")),
           ("10.09.2025", FIM("POLIGONAL ENGENHARIA LTDA", "ENCAMINHADO PARA A DISCIPLINAR"))])
    ok(("POLIGONAL ENGENHARIA LTDA", "08.01.2024", "10.09.2025") in [(t["setor"], t["inicio"], t.get("fim")) for t in f["trabalho"]],
       "4: com outro setor no dia: %s" % [(t["setor"], t["inicio"], t.get("fim")) for t in f["trabalho"]])
    # sem baixa depois, o "Deixa" do dia encerra o vínculo
    f = F([("12.08.2024", INI("POLIGONAL ENGENHARIA LTDA")),
           ("19.11.2024", INI("POLIGONAL ENGENHARIA LTDA")), ("19.11.2024", FIM("POLIGONAL ENGENHARIA LTDA", "DISPENSADO PELO EMPREGADOR"))])
    ok(all(t.get("fim") == "19.11.2024" for t in f["trabalho"]), "4: sem baixa posterior: %s" % f["trabalho"])
    # com novo início do setor antes da baixa posterior, nada muda
    f = F([("12.08.2024", INI("POLIGONAL ENGENHARIA LTDA")),
           ("19.11.2024", INI("POLIGONAL ENGENHARIA LTDA")), ("19.11.2024", FIM("POLIGONAL ENGENHARIA LTDA", "DISPENSADO PELO EMPREGADOR")),
           ("03.02.2025", INI("POLIGONAL ENGENHARIA LTDA")), ("14.07.2026", FIM("POLIGONAL ENGENHARIA LTDA", "DISPENSADO PELO EMPREGADOR"))])
    ok(("POLIGONAL ENGENHARIA LTDA", "03.02.2025", "14.07.2026") in [(t["setor"], t["inicio"], t.get("fim")) for t in f["trabalho"]]
       and not any(t["inicio"] == "12.08.2024" and t.get("fim") == "14.07.2026" for t in f["trabalho"]), "4: novo início no meio: %s" % f["trabalho"])
except Exception:
    import traceback
    traceback.print_exc()
    falhas.append("exceção")

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: revisão 7.15.2, comparação com conferências manuais (registro duplicado sem dias, remição de valor diferente ligada ao atestado, "
      "número dos autos com erro de digitação, reinscrição no mesmo setor)")
