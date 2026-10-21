"""Conferência 7.14.1, frente remição: desistência da escola registrada só na mudança de cela, certificado da Jornada da Leitura no
Cárcere, faixa de valor do ENEM/ENCCEJA, texto do pedido de atestado do trabalho em curso há mais de 90 dias, atestado que cita outra
unidade e matrícula cancelada na saída de outra unidade. Dados fictícios (sem nomes). Rodar: python teste_conf2_remicao.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_ficha as rf
import rspe_remicao as rrm
from teste_remicao_714 import R, T, A, F, HOJE

falhas = []


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def ler(evs):
    return rf.atualizar({"versao_leitura": 0, "eventos": [{"data": d, "texto": t} for d, t in evs]})


EV18 = [{"data": "01/03/2018", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}]  # execução desde 2018


def comp(r, f):
    o = rf.comparativo(r, f, HOJE)
    return o, o["fd_novo"]


def tipos(N):
    return {p["tipo"]: p for p in N["pontos"]}


try:
    # ---- 1) desistência da escola só na mudança de cela: o estudo termina ali (antes ficava aberto e era descartado depois de 1 ano) ----
    f = ler([("21.03.2019", "- Nesta data passa a frequentar o Setor Educacional no Módulo Inicial"),
             ("02.05.2019", "Mudança de Cela: UNIDADE X, Motivo: DESISTÊNCIA DA ESCOLA, Origem: R I/C11, Destino: R III/C09, Conforme Documento: CI 1.")])
    es = f.get("estudos") or []
    ok(len(es) == 1 and es[0]["inicio"] == "21.03.2019" and es[0]["fim"] == "02.05.2019" and es[0]["motivo_fim"] == "desistência da escola",
       "1: desistência na mudança de cela encerra o estudo: %s" % es)
    f2 = F([], [], [], estudos=es, data_impressao="02.10.2026")
    o, N = comp(R((10, "10/01/2024", None), eventos=EV18), f2)
    ok(any(x["fim"] == date(2019, 5, 2) and "Modulo Inicial" in x["txt"] for x in N["est_estim"]),
       "1: o estudo de 2019 entra na estimativa (sem certidão): %s" % N["est_estim"])

    # ---- 2) certificado da Jornada da Leitura no Cárcere: documento de leitura sem o número de obras (fora da conta, a conferir) ----
    f = ler([("20.11.2025", "EDUCAÇÃO: Peticionado Certificado da 5º Edição da Jornada da Leitura no Cárcere de 2024 no Sistema SEEU nos Autos Nº "
                            "0000001-11.2020.8.12.0001.")])
    lt = f.get("leituras") or []
    ok(len(lt) == 1 and not lt[0]["obras"] and not lt[0]["meses"], "2: Jornada da Leitura lida como leitura sem obras: %s" % lt)
    o, N = comp(R(), F([], [], [], leituras=lt))
    d = next((d for d in N["docs"] if d["tipo"] == "Leitura"), None)
    ok(d and d["num"].startswith("Jornada da Leitura no Cárcere") and d["dias"] is None and d["pet_ok"]
       and d["sem_valor"] == "certificado sem o número de obras", "2: documento da Jornada: %s" % d)
    ok("Jornada da Leitura" in tipos(N)["sem_valor"]["texto"] and N["comp"] == 0, "2: a conferir, fora da conta: %s" % N["pontos"])

    # ---- 3) exame sem valor na ficha: a faixa começa em 20 dias (uma área do ENEM: 100 dias ÷ 5) ----
    o, N = comp(R(), F([], [], [], exames=[{"exame": "ENEM 2025", "data": "20.02.2026", "certificado": False, "ano": 2025, "autos": ""}]))
    t3 = tipos(N)["exame"]["texto"]
    ok("de 20 dias, uma área do ENEM, a 133,33 dias" in t3 and "25 a 133" not in t3, "3: faixa do exame: %s" % t3)

    # ---- 4) trabalho em curso há mais de 90 dias, sem atestado: "pedir", com a impressão da ficha e há quantos dias está em curso ----
    f = F([T("PRENDEBEM", "01.07.2026")], [], [], data_impressao="02.10.2026")
    o, N = comp(R(), f)
    t4 = [x["t"] for x in N["onde"] if x["t"].startswith("Pedir atestado")]
    ok(t4 and "de 01/07/2026 a 02/10/2026 (impressão da ficha; em curso há 111 dias)" in t4[0] and "hoje" not in t4[0],
       "4: texto do pedido em curso: %s" % t4)
    f = F([T("PRENDEBEM", "01.09.2026")], [], [], data_impressao="02.10.2026")
    o, N = comp(R(), f)  # em curso há 49 dias: acompanhar (sem mudança)
    ok(N["acomp"] and not N["pedir_dias"], "4: até 90 dias continua acompanhar: %s" % N["onde"])

    # ---- 5) atestado que cita outra unidade, para período em que a ficha mostra o assistido em outra, sem trabalho: aviso ----
    ev5 = [("04.10.2022", "Entrada na Unidade Penal: ESTABELECIMENTO PENAL \"MAXIMO ROMERO\" DE JARDIM, Procedente: DP - INTERIOR, Conforme OF 1."),
           ("25.03.2024", "Nesta data foi emitido ATESTADO DE TRABALHO PRISIONAL Nº 24/2024/ST/EPRSAA-A/AGEPEN-MS, correspondente ao período de "
                          "14/08/2023 a 22/12/2023 Totalizando (oitenta e seis) dias trabalhados e 29 (vinte nove ) dias REMIDOS.")]
    f = F([], [A("024/2024", "25.03.2024", "14/08/2023", "22/12/2023", 29, 86)], ev5)
    o, N = comp(R(), f)
    p5 = tipos(N).get("outra_unidade")
    ok(p5 and p5["cor"] == "cinza" and "EPRSAA" in p5["texto"] and "Maximo Romero de Jardim" in p5["texto"],
       "5: aviso de atestado de outra unidade: %s" % N["pontos"])
    ok(any("024/2024 cita EPRSAA" in x["t"] for x in N["onde"]) and N["comp"] == 29, "5: em Onde, sem mudar a conta: %s" % N["onde"])
    # a mesma unidade (sigla pelas iniciais) ou trabalho registrado no período: sem aviso
    ev5b = [ev5[0], (ev5[1][0], ev5[1][1].replace("EPRSAA-A", "EPMR"))]
    o, N = comp(R(), F([], [A("024/2024", "25.03.2024", "14/08/2023", "22/12/2023", 29, 86)], ev5b))
    ok("outra_unidade" not in tipos(N), "5: sigla da própria unidade (EPMR): sem aviso: %s" % N["pontos"])
    o, N = comp(R(), F([T("ARTESANATO", "01.08.2023", "30.12.2023")], [A("024/2024", "25.03.2024", "14/08/2023", "22/12/2023", 29, 86)], ev5))
    ok("outra_unidade" not in tipos(N), "5: com trabalho no período: sem aviso: %s" % N["pontos"])

    # ---- 6) matrícula cancelada no dia da saída: a unidade de origem é a da certidão ----
    ev6 = [("14.05.2018", "Entrada na Unidade Penal: INSTITUTO PENAL DE CAMPO GRANDE, Procedente: PJFC - CAPITAL, Conforme CI 232."),
           ("12.02.2019", "Entrada na Unidade Penal: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Procedente: INSTITUTO PENAL DE CAMPO GRANDE, Conforme CI 36."),
           ("12.02.2019", "Saída da Unidade Penal: INSTITUTO PENAL DE CAMPO GRANDE, Destino: PENITENCIÁRIA DE DOIS IRMÃO DO BURITI, Motivo: Transferência de Presidio, Conforme CI 36."),
           ("12.02.2019", "EDUCAÇÃO: Cancelamento de Matrícula. Saida do Presidio")]
    f = F([], [], ev6, estudo_cancelado_sem_matricula=[{"data": "12.02.2019", "texto": "EDUCAÇÃO: Cancelamento de Matrícula. Saida do Presidio"}])
    o, N = comp(R(eventos=EV18), f)
    p6 = tipos(N)["estudo_sem_matricula"]
    ok("na saída do Instituto Penal de Campo Grande" in p6["texto"] and "certidão de frequência escolar ao Instituto Penal de Campo Grande" in p6["texto"]
       and "Dois Irm" not in p6["texto"], "6: unidade da matrícula cancelada: %s" % p6["texto"])
except Exception as e:  # noqa
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for x in falhas:
        print(" -", x)
    sys.exit(1)
print("ok: conferência 7.14.1, remição (desistência da escola, Jornada da Leitura, faixa do exame, pedido em curso, atestado de outra "
      "unidade, matrícula cancelada na saída)")
