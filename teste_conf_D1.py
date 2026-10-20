"""Conferência manual 7.13.0, frente D1 - remição ligada à sua origem: certidão de frequência escolar e curso de qualificação
peticionados explicam a remição decidida logo depois (não é "sem origem" nem trabalho); a decisão que soma atestado e leitura;
a remição sem atestado que não cabe no trabalho registrado antes dela fica "sem origem" (o trabalho do período, a conferir);
atestado contido em outro atestado cumulativo não se soma; atestado de período em que a execução estava interrompida pela
liberdade é de outra custódia; remição posterior sem origem que não alcança o atestado não o tira do total; excedente de uma
remição a maior abate o outro atestado não lançado; leitura remida pouco antes da petição registrada; exame com a referência
anterior ao ano da prova; lacuna sem os períodos de liberdade; referência tardia só com os dias do atestado e sem a progressão
desfeita por nova fixação de regime; perdas de remidos sem falta datada; "último atestado há 6 meses" a partir do início do
trabalho atual; matrícula cancelada sem matrícula registrada. (7.14: a remição deixou de ser ligada à origem; ficam os itens
de leitura e de lei.) Dados fictícios. Rodar: python teste_conf_D1.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_auditoria as ra
import rspe_ficha as rf

falhas = []
HOJE = date(2026, 10, 20)
PROC = "0009999-11.2020.8.12.0001"
INI = "TRABALHO: Iniciou atividade laboral, no setor de trabalho %s, conforme documento 1."
FIM = "TRABALHO: Deixa de trabalhar, no setor de trabalho %s, conforme documento 1, motivo: %s."


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


def FD(eventos, impressao="05/10/2026"):
    """Ficha com os campos derivados do histórico (certidões, cursos, leituras, exames, estudo), como na importação."""
    f = {"data_impressao": impressao, "eventos": [{"data": d, "texto": t} for d, t in eventos]}
    return rf.derivar(f, [dict(e, d=rf._dp(e["data"])) for e in f["eventos"]])


def rem(dias, dec, ref=None):
    return {"tipo": "REMIÇÃO", "complemento": "%s Dia(s) Remido(s)" % dias, "data_decisao": dec, "data_referencia": ref or dec, "situacao": "CONCEDIDO"}


def R(*incs, eventos=(), prisao="01/01/2020"):
    return {"processo_execucao": PROC, "_eventos": [{"data": prisao, "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}] + list(eventos),
            "_incidentes": list(incs), "_crimes": []}


def blocos(res):
    return [i for b in res.get("blocos") or [] for i in b["itens"]]


def alertas(C):
    return " | ".join(a["texto"] for a in C["alertas"])


try:
    # ---- 1: certidões de frequência peticionadas explicam as remições (referência no fim do semestre) ----
    f = FD([("02.03.2025", "EDUCAÇÃO: Matrículou-se na Série: 1ª FASE B ENSINO FUNDAMENTAL Turma: Período: Matutino"),
            ("06.03.2026", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 2º semestre de 2025, no Sistema SEEU nos Autos Nº 00099991120208120001."),
            ("20.08.2026", "EDUCAÇÃO: Peticionado Certidão de Frequência Escolar referente ao 1º semestre de 2026, no Sistema SEEU nos Autos Nº 0009999-11.2020.8.12.0001.")])
    ok([(c["semestre"], c["ano"]) for c in f["certidoes_estudo"]] == [(2, 2025), (1, 2026)], "1: certidões lidas %r" % f["certidoes_estudo"])
    # (7.14: os itens 1 - remição atribuída às certidões -, 2 a 5 e 7 a 13 ligavam a remição do RSPE à sua origem na ficha, o que o
    # programa não faz mais; fica a leitura, a outra custódia, as perdas e a matrícula cancelada)

    # ---- 6: atestado de período em que a execução estava interrompida pela liberdade: outra custódia ----
    f = FD([("29.07.2016", "Emitido Atestado de Trabalho nº 499, período de 14/06/2016 a 28/07/2016, 39 dias trabalhados e 13 dias remidos.")])
    r = R(prisao="20/04/2015", eventos=[{"data": "27/05/2015", "tipo": "INTERRUPÇÃO", "motivo": "LIBERDADE PROVISÓRIA"},
                                         {"data": "17/05/2017", "tipo": "PRISÃO/INÍCIO DE CUMPRIMENTO", "motivo": "PRISÃO"}])
    N = rf.comparativo(r, f, HOJE)["fd_novo"]
    d = N["docs"][0]
    ok(d["fora"].startswith("período em que esta execução estava interrompida (liberdade provisória") and d["cor"] == "cinza" and N["comp"] == 0,
       "6: atestado da liberdade %r" % d)

    # ---- 14: perda sem falta datada antes da falta, somadas acima de 1/3 ----
    incs = [rem(250, "01/08/2014"), {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "complemento": "83 Dia(s)", "data_decisao": "24/08/2015", "situacao": "CONCEDIDO"},
            {"tipo": "FALTA GRAVE", "complemento": "Fuga em 18/11/2019", "data_decisao": "10/01/2020", "data_referencia": "18/11/2019", "situacao": "CONCEDIDO"},
            {"tipo": "DIAS PERDIDOS NA REMIÇÃO", "complemento": "26 Dia(s)", "data_decisao": "10/01/2020", "situacao": "CONCEDIDO"}]
    its = ra._perda_remidos(incs, 109)
    tits = " | ".join(i["titulo"] for i in its)
    ok("sem falta grave datada no RSPE (decisão de 24/08/2015)" in tits and "somadas acima de 1/3" in tits, "14: perdas %s" % tits)
    ok(not any(i["nivel"] == "info" and "Dentro do limite" in (i.get("detalhe") or "") for i in its), "14: 'dentro do limite' contraditório")

    # ---- 15: trabalho atual iniciado há menos de 6 meses: o atestado antigo não está "vencido" ----
    f = FD([("01.03.2019", INI % "FAXINA"), ("31.08.2019", FIM % ("FAXINA", "A PEDIDO")),
            ("05.09.2019", "Emitido Atestado de Trabalho nº 100/2019, período de 01/03/2019 a 31/08/2019, 155 dias trabalhados e 51 dias remidos."),
            ("15.08.2026", INI % "PRENDEBEM")])
    out = rf.comparativo(R(rem(51, "10/10/2019", "31/08/2019")), f, HOJE)
    ok("Último atestado há 6 meses" not in out["fd_sit"], "15: último atestado vencido com trabalho novo %r" % out["fd_sit"])

    # ---- 16: matrícula cancelada sem a matrícula registrada: estudo a conferir ----
    f = FD([("12.02.2019", "EDUCAÇÃO: Cancelamento de Matrícula. Saida do Presidio")])
    out = rf.comparativo(R(prisao="02/03/2018"), f, HOJE)
    ok("matrícula cancelada em 12/02/2019" in (out.get("fd_sit_det") or "") and out["fd_cor"] == "amarelo", "16: estudo sem matrícula %r" % out.get("fd_sit_det"))
except Exception as e:
    import traceback
    traceback.print_exc()
    falhas.append("exceção: %r" % e)
print("\n".join(falhas) if falhas else "ok: conferência 7.13.0 - D1 (ajustada à 7.14: leitura das certidões, outra custódia, perdas, último atestado, matrícula)")
sys.exit(1 if falhas else 0)
