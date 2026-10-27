"""Teste da terceira conferência (7.14.2), frente indulto e comutação: com vários impedimentos, o motivo objetivo (pena, crime,
prazo) antes da fuga não homologada; comutação com o indulto do XV indeferido volta à soma total; pena extinta depois da data que
só aumentaria o requisito ("não atinge"); explicação da comutação igual ao detalhamento; tempo dos eventos sem origem (comutação
firme, indulto a verificar); grupo de impeditivos com fatos diferentes (conta crime a crime); rótulo de quem estava preso depois
do livramento; reincidência pela ficha (pena em cumprimento antes do fato, extinta depois) e "faltavam" pelos eventos com
diferença pequena da âncora. Casos hipotéticos, nomes fictícios.
Rodar: python teste_conf3_indulto.py"""
import sys
import types
from datetime import date

sys.modules.setdefault("webview", types.ModuleType("webview"))
import rspe_decretos as rd
import rspe_reincidencia as rr
import rspe_scraper as rs

falhas = []
HOJE = date(2026, 10, 21)
D = rs.to_date


def ok(cond, msg):
    if not cond:
        falhas.append(msg)


P1 = "0000001-11.2004.8.12.0001"
PR = "PRISÃO/INÍCIO DE CUMPRIMENTO"
IN = "INTERRUPÇÃO"


def crime(**kw):
    c = {"processo_criminal": P1, "lei": "2848/40 - Código Penal", "artigo": "ART 155: Furto",
         "tipo_penal": "CAPUT: Subtrair, Reclusão: 1 a 4 anos", "pena_imposta": "1 ano(s), 0 mês(es) e 0 dia(s)",
         "pena_total_processo": "", "data_infracao": "10/01/2004", "data_sentenca": "10/06/2004", "transito_mp": "10/07/2004",
         "transito_processo": "10/07/2004", "extinto": "Não", "suspenso": "Não", "vga": "N", "resultado_morte": "N",
         "reincidente_comum": "N", "reincidente_especifico": "N", "comando_orcrim": "N", "regime_sentenca": "Fechado"}
    c.update(kw)
    return c


def ev(tipo, motivo, data):
    return {"tipo": tipo, "motivo": motivo, "data": data, "processos": P1}


def reg(crimes, eventos, pena_total, cumprida="", incid=None, ger="05/10/2026"):
    return {"nome": "T", "processo_execucao": "X", "pena_total": pena_total, "pena_cumprida": cumprida, "pena_remanescente": "",
            "data_geracao_rspe": ger, "termino_previsao_seeu": "", "data_nascimento": "01/01/1980", "_sexo": "M",
            "status_execucao": "ATIVO", "regime_atual": "Fechado - ATIVO", "_crimes": crimes, "_eventos": eventos,
            "_incidentes": incid or [], "total_interrupcoes": ""}


def dec(r, ano):
    return next(x for x in rd.avaliar(r, HOJE)["decretos"] if str(x["id"]) == ano)


# 1. (I1) Decreto 8.940/2016: pena acima do teto de 12 anos e fuga não homologada na janela - o motivo objetivo vem primeiro
cs = [crime(pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)", processo_criminal="000000%d-11.2004.8.12.0001" % n) for n in range(1, 5)]
evs = [ev(PR, "PRISÃO DEFINITIVA", "10/07/2004"), ev(IN, "FUGA", "15/12/2015"), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "05/02/2016")]
x = dec(reg(cs, evs, "16a0m0d"), "2016")
# (7.14.8) o art. 9º, p. ú., do Decreto 8.940/2016 posterga a declaração até a apuração: a fuga não submetida ao juízo não impede
# (fica a verificar) - o motivo é só o objetivo
ok(x["s"] == "nao" and (x.get("mot") or "").startswith("pena total"),
   "1: motivo objetivo (pena acima do teto): %s | %s" % (x["s"], x.get("mot")))
ok((x.get("mot_c") or "").startswith("Pena total"), "1: o motivo curto é o objetivo: %s" % x.get("mot_c"))
cs1 = [crime(pena_imposta="4 ano(s), 0 mês(es) e 0 dia(s)")]
x1 = dec(reg(cs1, evs, "4a0m0d"), "2016")
ok(x1["s"] == "ver" and "posterga" in (x1.get("mot") or ""), "1: 2016, fuga não apurada - a verificar: %s" % x1.get("mot"))
# o mesmo ordenamento num decreto em que a fuga sem homologação impede (Decreto 6.294/2007, art. 4º: não exige apuração)
evs7 = [ev(PR, "PRISÃO DEFINITIVA", "10/07/2004"), ev(IN, "FUGA", "15/12/2006"), ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "05/02/2007")]
x7 = dec(reg(cs, evs7, "16a0m0d"), "2007")
ok(x7["s"] == "nao" and (x7.get("mot") or "").startswith("faltavam") and "também falta grave" in (x7.get("mot") or ""),
   "1: motivo objetivo antes da fuga não homologada: %s | %s" % (x7["s"], x7.get("mot")))
# sem impedimento objetivo, a falta continua sendo o motivo
x1 = dec(reg(cs1, evs7, "4a0m0d"), "2007")
ok(x1["s"] == "nao" and (x1.get("mot") or "").startswith("falta grave"), "1: só a falta impede - ela é o motivo: %s" % x1.get("mot"))

# 2. (I2, #14) indulto do XV indeferido no RSPE: a comutação recalculada "sem as penas indultadas" volta à conta da soma total
r2 = {"indulto_2024": "POSSÍVEL (parcial): art. 9º, XV",
      "comutacao_2024": "A VERIFICAR: art. 13 - sem as penas indultadas pelo XV (art. 155 CP), a pena dos demais crimes é 9a4m5d e o "
                        "requisito (1/4 = 2a4m2d) está cumprido (7a11m29d); recalcular a comutação sobre ela",
      "comutacao_2024_se_indeferido": "não atinge (1/4 até 25/12/2024)",
      "comutacao_2024_detalhe": "✘ Requisito: 1/4 da pena.\nO indulto do inciso XV alcança só parte dos crimes; a comutação incide sobre a "
                                "pena dos demais - recalcular sem as penas indultadas.",
      "comutacao_2024_explica": "Decreto 12.338/2024, art. 13.\nO indulto do inciso XV alcança só parte dos crimes; a comutação incide sobre "
                                "a pena dos demais - recalcular sem as penas indultadas."}
inc2 = [{"tipo": "INDULTO", "complemento": "Decreto 12.338/2024", "situacao": "NÃO CONCEDIDO", "data_decisao": "19/01/2026",
         "data_referencia": "19/01/2026"}]
rs.aplicar_decisoes_decretos(r2, inc2)
ok(r2["comutacao_2024"].startswith("não atinge") and r2.get("comutacao_2024_status") == "nao",
   "2: indulto indeferido - comutação pela soma total: %s" % r2["comutacao_2024"])
ok("recalcular sem as penas indultadas" not in r2["comutacao_2024_detalhe"] + r2["comutacao_2024_explica"]
   and "Indulto indeferido no RSPE em 19/01/2026" in r2["comutacao_2024_explica"],
   "2: detalhamento e explicação dizem o indeferimento: %s" % r2["comutacao_2024_explica"])

# 3. (I3, #9) explicação da comutação segue o detalhamento com o indulto indeferido
r3 = {"indulto_2024": "POSSÍVEL: art. 9º, VII", "comutacao_2024": "prejudicada: indulto cabível (art. 13, § 5º)",
      "comutacao_2024_se_indeferido": "POSSÍVEL: art. 13 (1/5 do remanescente)",
      "comutacao_2024_detalhe": "✔ Requisito.\nPrejudicada: o indulto é cabível e prevalece (art. 13, § 5º).",
      "comutacao_2024_explica": "Decreto 12.338/2024, art. 13.\n✔ Requisito.\nPrejudicada: o indulto é cabível e prevalece (art. 13, § 5º)."}
rs.aplicar_decisoes_decretos(r3, [dict(inc2[0], data_decisao="14/10/2025", data_referencia="14/10/2025")])
ok("Prejudicada: o indulto é cabível" not in r3["comutacao_2024_explica"] and "Indulto indeferido" in r3["comutacao_2024_explica"],
   "3: a explicação não diz mais que o indulto é cabível: %s" % r3["comutacao_2024_explica"])

# 4. (I2, #8) pena extinta depois da data, fora da conta da comutação não atingida: somá-la só aumenta o requisito
ce = crime(data_infracao="01/03/2018", data_sentenca="01/06/2019", transito_mp="01/07/2019", transito_processo="01/07/2019",
           extinto="Sim", data_extincao="07/01/2026", extincao_motivo="PRESCRIÇÃO", artigo="ART 147: Ameaça")
out4 = {"comutacao_2024": "não atinge (1/4 até 25/12/2024; cumprido 0a3m15d)", "comutacao_2024_status": "nao",
        "indulto_2024": "não atinge nenhum inciso nesta data"}
rs._extinta_depois(out4, [ce], "2024", D("25/12/2024"))
ok(out4["comutacao_2024"].startswith("não atinge") and "só aumentaria o requisito" in out4["comutacao_2024"]
   and out4["comutacao_2024_status"] == "nao", "4: a comutação continua 'não atinge': %s" % out4["comutacao_2024"])
ok(out4["indulto_2024"].startswith("A VERIFICAR"), "4: o indulto segue a verificar com a pena extinta fora da conta")

# 5. (I5, #15) impeditivos de fatos diferentes no mesmo grupo: a nota diz os fatos e a conta crime a crime
per = [(D("01/01/2016"), None)]
imp = [crime(artigo="ART 157: Roubo", pena_imposta="4a2m0d", data_infracao="24/08/2017"),
       crime(artigo="ART 157: Roubo", pena_imposta="10a8m10d", data_infracao="28/02/2020")]
_c, _n = rs.cumprido_imputavel_impeditivos(imp, 3600, per, [], D("25/12/2025"))
ok("fatos de 24/08/2017 e 28/02/2020" in _n and "crime a crime" in _n, "5: nota do grupo com dois fatos: %s" % _n)

# 6. (I6, #11) reincidência pela ficha: pena de outro processo em cumprimento antes do fato e extinta depois dele
ficha = {"eventos": [
    {"data": "10.11.2020", "texto": "Saída da Unidade Penal: PENITENCIÁRIA X, Motivo: Progressão de Regime, Conforme Ofício: AUTOS0002516-90.2008.8.12.0005."},
    {"data": "02.05.2022", "texto": "Entrada na Unidade Penal: ESTABELECIMENTO Y, Conforme OF 0002516-90.2008.8.12.0005. para cumprimento de pena em Regime SEMIABERTO."},
    {"data": "25.07.2024", "texto": "PENA EXTINTA CONFORME DECISÃO DA VEPIN, EM 19/07/2024, Autos nº. 0002516-90.2008.8.12.0005."}]}
ext = rr.extincoes_ficha(ficha)
ok(len(ext) == 1 and ext[0]["data"] == D("19/07/2024") and ext[0].get("cumprimento_desde") == D("10/11/2020"),
   "6: extinção lida com a data da decisão e o início do cumprimento: %s" % ext)
c6 = crime(processo_criminal="0900267-38.2024.8.12.0052", data_infracao="01/07/2024", data_sentenca="06/04/2025",
           transito_mp="28/07/2025", transito_processo="28/07/2025", reincidente_comum="S")
R = rr.reincidencia_pelas_datas(c6, [c6], None, ext)
ok(R["estado"] == "reincidente" and R["fonte"] == "ficha" and "em cumprimento desde 10/11/2020" in R["motivo"],
   "6: reincidente pela ficha: %s" % R)
# extinção e cumprimento só depois do fato: sem base na ficha
R2 = rr.reincidencia_pelas_datas(dict(c6, data_infracao="01/07/2020"), [c6], None, ext)
ok(R2["fonte"] != "ficha", "6: cumprimento posterior ao fato não dá reincidência: %s" % R2["fonte"])

# 7. (I6, #17) eventos pouco acima da âncora (menos de 180 dias): o "não" é o mesmo, e o "faltavam" mostrado é o dos eventos
c7 = crime(pena_imposta="0 ano(s), 6 mês(es) e 0 dia(s)", data_infracao="14/09/2013", data_sentenca="10/06/2014",
           transito_mp="10/07/2014", transito_processo="10/07/2014", reincidente_comum="S", artigo="ART 306: Embriaguez",
           lei="9503/97 - Código de Trânsito")
e7 = [ev(PR, "PRISÃO EM FLAGRANTE", "14/09/2013"), ev(IN, "LIBERDADE PROVISÓRIA", "15/09/2013"), ev(PR, "PRISÃO EM FLAGRANTE", "21/11/2023")]
# SEEU: cumprido hoje = custódia desde 21/11/2023 menos 9 dias (âncora abaixo dos eventos)
_hoje7 = D("05/10/2026")
_dias = (_hoje7 - D("21/11/2023")).days + 1 + 2 - 9
r7 = reg([c7], e7, "0a6m0d", cumprida=rs.dias_para_pena(_dias))
x7 = dec(r7, "2023")
ok(x7["s"] == "nao" and "contagem pelos eventos" in (x7.get("mot") or ""), "7: faltavam pelos eventos: %s | %s" % (x7["s"], x7.get("mot")))

# 8. (I6, #6) preso de novo depois do livramento, sem revogação registrada: o rótulo diz a custódia, não "regime Livramento"
P2 = "0000001-11.2015.8.12.0001"
c8 = crime(processo_criminal=P2, artigo="ART 157: Roubo", tipo_penal="§ 2º, II: concurso", pena_imposta="14 ano(s), 0 mês(es) e 0 dia(s)",
           data_infracao="10/01/2015", data_sentenca="10/06/2015", transito_mp="10/07/2015", transito_processo="10/07/2015", vga="S",
           reincidente_comum="S")
e8 = [ev(PR, "PRISÃO DEFINITIVA", "08/03/2017"), ev(IN, "LIVRAMENTO CONDICIONAL", "10/11/2020"),
      ev(PR, "RECAPTURA/REINÍCIO DE CUMPRIMENTO", "17/05/2024")]
i8 = [{"tipo": "LIVRAMENTO CONDICIONAL", "complemento": "", "situacao": "CONCEDIDO", "data_decisao": "09/11/2020", "data_referencia": "09/11/2020"}]
campos8 = {"pena_total": "14a0m0d", "pena_cumprida": "6a0m0d", "data_geracao_rspe": "05/10/2026", "regime_atual": "Livramento Condicional - ATIVO",
           "_sexo": "M", "data_nascimento": "01/01/1980", "status_execucao": "ATIVO", "total_interrupcoes": ""}
o8 = rs.analise_decretos(campos8, [c8], e8, i8, HOJE)
l8 = (o8.get("indulto_2024_detalhe") or "").split("\n")[0]
ok(l8.startswith("Situação em 25/12/2024: estava preso desde 17/05/2024") and "regime formal no SEEU: livramento condicional" in l8
   and "regime Livramento" not in l8, "8: rótulo da situação: %s" % l8)

if falhas:
    print("FALHAS (%d):" % len(falhas))
    for f_ in falhas:
        print(" -", f_)
    sys.exit(1)
print("teste_conf3_indulto: ok")
